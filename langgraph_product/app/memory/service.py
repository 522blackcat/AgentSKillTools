"""三层记忆服务。

短期记忆来自最近消息，摘要记忆来自 session summary，长期记忆来自 user_memories。
runtime 会把这些内容拼成 prompt context。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ChatMessage, ChatSession, UserMemory
from app.knowledge.embedding import cosine, embed_text, lexical_score
from app.schemas import MemoryCreate


RECENT_MESSAGE_LIMIT = 8
SUMMARY_TRIGGER_MESSAGES = 12
SUMMARY_RECENT_KEEP = 6


@dataclass(frozen=True)
class MemoryContext:
    recent_messages: list[dict]
    summary: str
    long_term_memories: list[dict]

    def to_prompt_context(self) -> str:
        parts = []
        if self.summary:
            parts.append(f"【会话摘要】\n{self.summary}")
        if self.recent_messages:
            history = "\n".join(
                f"{item['role']}: {item['content']}" for item in self.recent_messages
            )
            parts.append(f"【最近对话】\n{history}")
        if self.long_term_memories:
            memories = "\n".join(
                f"- [{item['category']}] {item['key']}: {item['value']}"
                for item in self.long_term_memories
            )
            parts.append(f"【长期记忆】\n{memories}")
        return "\n\n".join(parts)


def create_memory(db: Session, data: MemoryCreate) -> UserMemory:
    existing = db.scalars(
        select(UserMemory).where(
            UserMemory.tenant_id == data.tenant_id,
            UserMemory.user_id == data.user_id,
            UserMemory.category == data.category,
            UserMemory.memory_key == data.memory_key,
        )
    ).first()
    if existing is None:
        memory = UserMemory(
            tenant_id=data.tenant_id,
            user_id=data.user_id,
            category=data.category,
            memory_key=data.memory_key,
            memory_value=data.memory_value,
            confidence=data.confidence,
            source_session_id=data.source_session_id,
            embedding=embed_text(f"{data.memory_key}: {data.memory_value}"),
            is_active=True,
        )
        db.add(memory)
    else:
        memory = existing
        memory.memory_value = data.memory_value
        memory.confidence = data.confidence
        memory.source_session_id = data.source_session_id
        memory.embedding = embed_text(f"{data.memory_key}: {data.memory_value}")
        memory.is_active = True
        memory.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(memory)
    return memory


def load_memory_context(
    db: Session,
    tenant_id: str,
    user_id: str,
    session_id: str | None,
    query: str,
    recent_limit: int = RECENT_MESSAGE_LIMIT,
    long_term_top_k: int = 5,
) -> MemoryContext:
    recent_messages = load_recent_messages(db, tenant_id, session_id, recent_limit)
    summary = load_session_summary(db, tenant_id, session_id)
    long_term = search_memories(db, tenant_id, user_id, query, long_term_top_k)
    return MemoryContext(recent_messages=recent_messages, summary=summary, long_term_memories=long_term)


def load_recent_messages(
    db: Session,
    tenant_id: str,
    session_id: str | None,
    limit: int = RECENT_MESSAGE_LIMIT,
) -> list[dict]:
    if not session_id:
        return []
    statement = (
        select(ChatMessage)
        .where(ChatMessage.tenant_id == tenant_id, ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    rows = list(db.scalars(statement).all())
    rows.reverse()
    return [{"role": row.role, "content": row.content, "metadata": row.metadata_json} for row in rows]


def load_session_summary(db: Session, tenant_id: str, session_id: str | None) -> str:
    if not session_id:
        return ""
    session = db.get(ChatSession, session_id)
    if session is None or session.tenant_id != tenant_id:
        return ""
    return session.summary


def save_turn(
    db: Session,
    tenant_id: str,
    user_id: str,
    session_id: str | None,
    user_input: str,
    assistant_output: str,
) -> None:
    if not session_id:
        return
    db.add(
        ChatMessage(
            tenant_id=tenant_id,
            session_id=session_id,
            role="user",
            content=user_input,
            token_count=_estimate_tokens(user_input),
        )
    )
    db.add(
        ChatMessage(
            tenant_id=tenant_id,
            session_id=session_id,
            role="assistant",
            content=assistant_output,
            token_count=_estimate_tokens(assistant_output),
        )
    )
    db.flush()
    maybe_update_summary(db, tenant_id, user_id, session_id)
    db.commit()


def maybe_update_summary(db: Session, tenant_id: str, user_id: str, session_id: str) -> None:
    session = db.get(ChatSession, session_id)
    if session is None or session.tenant_id != tenant_id or session.user_id != user_id:
        return
    statement = (
        select(ChatMessage)
        .where(ChatMessage.tenant_id == tenant_id, ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = list(db.scalars(statement).all())
    if len(messages) < SUMMARY_TRIGGER_MESSAGES:
        session.updated_at = datetime.now(timezone.utc)
        return
    old_messages = messages[:-SUMMARY_RECENT_KEEP]
    compacted = _compact_messages(session.summary, old_messages)
    session.summary = compacted
    session.updated_at = datetime.now(timezone.utc)


def search_memories(db: Session, tenant_id: str, user_id: str, query: str, top_k: int = 5) -> list[dict]:
    query_vector = embed_text(query)
    statement = select(UserMemory).where(
        UserMemory.tenant_id == tenant_id,
        UserMemory.user_id == user_id,
        UserMemory.is_active.is_(True),
    )
    scored = []
    for memory in db.scalars(statement).all():
        text = f"{memory.memory_key}: {memory.memory_value}"
        score = cosine(query_vector, memory.embedding or []) + lexical_score(query, text) * 0.2
        scored.append((score, memory))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "id": memory.id,
            "category": memory.category,
            "key": memory.memory_key,
            "value": memory.memory_value,
            "confidence": float(memory.confidence),
            "score": score,
        }
        for score, memory in scored[:top_k]
    ]


def _compact_messages(existing_summary: str, messages: list[ChatMessage]) -> str:
    lines = [existing_summary.strip()] if existing_summary.strip() else []
    transcript = "\n".join(f"{message.role}: {message.content}" for message in messages)
    if transcript:
        lines.append(transcript)
    combined = "\n".join(lines)
    if len(combined) <= 2000:
        return combined
    return combined[-2000:]


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
