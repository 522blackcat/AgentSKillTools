from fastapi.testclient import TestClient

from app import settings
from app.database import SessionLocal
from app.main import app
from app.memory.service import load_memory_context
from app.models import ChatMessage, ChatSession, UserMemory


def test_agent_invoke_persists_three_layer_memory() -> None:
    settings.MODEL_PROVIDER = "stub"
    with TestClient(app) as client:
        first = client.post(
            "/v1/agent/invoke",
            json={
                "tenant_id": "tenant-memory",
                "user_id": "user-memory",
                "message": "Remember I prefer concise answers.",
            },
        )
        assert first.status_code == 200, first.text
        session_id = first.json()["memory"]["session_id"]

        second = client.post(
            "/v1/agent/invoke",
            json={
                "tenant_id": "tenant-memory",
                "user_id": "user-memory",
                "session_id": session_id,
                "message": "Use my preference.",
            },
        )
        assert second.status_code == 200, second.text
        assert second.json()["memory"]["recent_messages"]

        with SessionLocal() as db:
            messages = db.query(ChatMessage).filter_by(session_id=session_id).all()
            session = db.get(ChatSession, session_id)
            memories = db.query(UserMemory).filter_by(
                tenant_id="tenant-memory",
                user_id="user-memory",
            ).all()
            context = load_memory_context(
                db,
                "tenant-memory",
                "user-memory",
                session_id,
                "concise answers",
            )
        assert len(messages) == 4
        assert session is not None
        assert session.summary
        assert memories
        assert context["long_term_memories"]
