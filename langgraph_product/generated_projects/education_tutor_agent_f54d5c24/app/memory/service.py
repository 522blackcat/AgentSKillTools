"""Three-layer memory service.

Layers:
- short-term: recent chat_messages
- summary: chat_sessions.summary
- long-term: user_memories
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatSession, UserMemory
from app.rag.embedding import embed_query


MEMORY_LAYERS = {
    "short_term": "chat_messages",
    "summary": "chat_sessions.summary",
    "long_term": "user_memories",
}


@dataclass
class MemoryContext:
    session_id: str
    summary: str
    recent_messages: list[dict[str, Any]]
    long_term_memories: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "summary": self.summary,
            "recent_messages": self.recent_messages,
            "long_term_memories": self.long_term_memories,
        }


def ensure_session(
    db: Session,
    tenant_id: str,
    user_id: str,
    session_id: str | None = None,
) -> ChatSession:
    if session_id:
        session = db.get(ChatSession, session_id)
        if session is not None and session.tenant_id == tenant_id and session.user_id == user_id:
            return session
    session = ChatSession(tenant_id=tenant_id, user_id=user_id or "anonymous", title="Agent chat")
    db.add(session)
    db.flush()
    return session


def load_memory_context(
    db: Session,
    tenant_id: str,
    user_id: str,
    session_id: str | None,
    query: str,
    recent_limit: int = 8,
    memory_limit: int = 5,
) -> dict[str, Any]:
    session = ensure_session(db, tenant_id, user_id or "anonymous", session_id)
    recent_rows = list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.tenant_id == tenant_id, ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(recent_limit)
        ).all()
    )
    recent_messages = [
        {
            "role": row.role,
            "content": row.content,
            "created_at": row.created_at.isoformat(),
        }
        for row in reversed(recent_rows)
    ]
    long_term_memories = search_memories(db, tenant_id, user_id or "anonymous", query, memory_limit)
    return MemoryContext(
        session_id=session.id,
        summary=session.summary,
        recent_messages=recent_messages,
        long_term_memories=long_term_memories,
    ).to_dict()


def save_turn(
    db: Session,
    tenant_id: str,
    user_id: str,
    session_id: str | None,
    user_input: str,
    assistant_output: str,
) -> str:
    session = ensure_session(db, tenant_id, user_id or "anonymous", session_id)
    db.add(
        ChatMessage(
            tenant_id=tenant_id,
            session_id=session.id,
            user_id=user_id or "anonymous",
            role="user",
            content=user_input,
            token_count=estimate_tokens(user_input),
        )
    )
    db.add(
        ChatMessage(
            tenant_id=tenant_id,
            session_id=session.id,
            user_id=user_id or "anonymous",
            role="assistant",
            content=assistant_output,
            token_count=estimate_tokens(assistant_output),
        )
    )
    update_summary(session, user_input, assistant_output)
    maybe_extract_memory(db, tenant_id, user_id or "anonymous", session.id, user_input)
    db.commit()
    return session.id


def search_memories(
    db: Session,
    tenant_id: str,
    user_id: str,
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    query_vector = embed_query(query)
    rows = list(
        db.scalars(
            select(UserMemory).where(
                UserMemory.tenant_id == tenant_id,
                UserMemory.user_id == user_id,
                UserMemory.is_active.is_(True),
            )
        ).all()
    )
    scored = sorted(
        ((cosine(query_vector, row.embedding), row) for row in rows),
        key=lambda item: item[0],
        reverse=True,
    )
    return [
        {
            "category": row.category,
            "key": row.memory_key,
            "value": row.memory_value,
            "confidence": float(row.confidence),
            "score": round(float(score), 6),
        }
        for score, row in scored[:top_k]
    ]


def maybe_extract_memory(
    db: Session,
    tenant_id: str,
    user_id: str,
    session_id: str,
    user_input: str,
) -> None:
    lowered = user_input.lower()
    markers = ["remember ", "记住", "偏好", "preference"]
    if not any(marker in lowered for marker in markers):
        return
    key = "user_note"
    value = user_input.strip()[:1000]
    existing = db.scalars(
        select(UserMemory).where(
            UserMemory.tenant_id == tenant_id,
            UserMemory.user_id == user_id,
            UserMemory.category == "preference",
            UserMemory.memory_key == key,
        )
    ).first()
    if existing is None:
        db.add(
            UserMemory(
                tenant_id=tenant_id,
                user_id=user_id,
                category="preference",
                memory_key=key,
                memory_value=value,
                confidence=1.0,
                source_session_id=session_id,
                embedding=embed_query(value),
            )
        )
    else:
        existing.memory_value = value
        existing.embedding = embed_query(value)


def update_summary(session: ChatSession, user_input: str, assistant_output: str) -> None:
    turn = f"User: {user_input[:160]}\nAssistant: {assistant_output[:160]}"
    session.summary = (session.summary + "\n" + turn).strip()[-1200:]


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)
