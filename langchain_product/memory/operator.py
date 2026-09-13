"""Database operators and persistent LangChain chat history."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4
from typing import Any

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict
from sqlalchemy import create_engine, desc, select
from sqlalchemy.orm import sessionmaker

from ..token_utils import clip_text, token_count
from .models import Base, ChatSessionRecord, ExtractedMemory, UserMemoryRecord


class DatabaseChatMessageHistory(BaseChatMessageHistory):
    """Persistent history; prompt limits never delete stored messages."""

    def __init__(
        self,
        session_factory,
        user_id: str,
        session_id: str,
        max_prompt_tokens: int | None = None,
    ):
        self._session_factory = session_factory
        self.user_id = user_id
        self.session_id = session_id
        self.max_prompt_tokens = max_prompt_tokens
        with self._session_factory() as db_session:
            record = self._get_record(db_session)
            self._messages = list(messages_from_dict(json.loads(record.messages_json)))
            self._summary = record.summary

    @property
    def messages(self) -> list[BaseMessage]:
        if self.max_prompt_tokens is None:
            return list(self._messages)
        selected: list[BaseMessage] = []
        used_tokens = 0
        for message in reversed(self._messages):
            message_tokens = token_count(str(message.content))
            if selected and used_tokens + message_tokens > self.max_prompt_tokens:
                break
            remaining_tokens = self.max_prompt_tokens - used_tokens
            if message_tokens > remaining_tokens:
                message = message.model_copy(
                    update={"content": clip_text(str(message.content), remaining_tokens)}
                )
                message_tokens = token_count(str(message.content))
            selected.append(message)
            used_tokens += message_tokens
        return list(reversed(selected))

    @property
    def summary(self) -> str:
        return self._summary

    @summary.setter
    def summary(self, value: str) -> None:
        self._summary = value

    def add_messages(self, messages: list[BaseMessage]) -> None:
        self._messages.extend(messages)
        self._save()

    def clear(self) -> None:
        self._messages = []
        self._summary = ""
        self._save()

    def _get_record(self, db_session) -> ChatSessionRecord:
        record = db_session.scalar(
            select(ChatSessionRecord).where(
                ChatSessionRecord.user_id == self.user_id,
                ChatSessionRecord.session_id == self.session_id,
            )
        )
        if record is None:
            record = ChatSessionRecord(
                user_id=self.user_id,
                session_id=self.session_id,
                updated_at=datetime.now(timezone.utc),
            )
            db_session.add(record)
            db_session.commit()
        return record

    def _save(self) -> None:
        with self._session_factory() as db_session:
            record = self._get_record(db_session)
            record.messages_json = json.dumps(
                messages_to_dict(self._messages), ensure_ascii=False
            )
            record.summary = self._summary
            record.updated_at = datetime.now(timezone.utc)
            db_session.commit()


class DatabaseSessionHistoryStore:
    """Persistence gateway keyed by authenticated user and chat window."""

    def __init__(self, database_url: str | None = None, create_tables: bool = True):
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", "sqlite:///chat_memory.db"
        )
        connect_args = (
            {"check_same_thread": False}
            if self.database_url.startswith("sqlite")
            else {}
        )
        self.engine = create_engine(self.database_url, connect_args=connect_args)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        if create_tables:
            Base.metadata.create_all(self.engine)
        self._lock = RLock()

    def get(
        self,
        user_id: str,
        session_id: str,
        max_prompt_tokens: int | None = None,
    ) -> DatabaseChatMessageHistory:
        if not user_id or not user_id.strip():
            raise ValueError("user_id must not be empty")
        if not session_id or not session_id.strip():
            raise ValueError("session_id must not be empty")
        with self._lock:
            return DatabaseChatMessageHistory(
                self.session_factory, user_id, session_id, max_prompt_tokens
            )

    def create_window(self, user_id: str) -> str:
        session_id = str(uuid4())
        self.get(user_id, session_id)
        return session_id

    def list_windows(self, user_id: str) -> list[dict[str, Any]]:
        if not user_id or not user_id.strip():
            raise ValueError("user_id must not be empty")
        with self.session_factory() as db_session:
            records = db_session.scalars(
                select(ChatSessionRecord)
                .where(ChatSessionRecord.user_id == user_id)
                .order_by(desc(ChatSessionRecord.updated_at))
            ).all()
            return [
                {
                    "session_id": record.session_id,
                    "updated_at": record.updated_at.isoformat(),
                    "message_count": len(
                        messages_from_dict(json.loads(record.messages_json))
                    ),
                }
                for record in records
            ]

    def list_memories(
        self,
        user_id: str,
        query: str = "",
        max_tokens: int | None = None,
    ) -> list[dict[str, Any]]:
        with self.session_factory() as db_session:
            records = db_session.scalars(
                select(UserMemoryRecord)
                .where(
                    UserMemoryRecord.user_id == user_id,
                    UserMemoryRecord.is_active.is_(True),
                )
                .order_by(UserMemoryRecord.category, UserMemoryRecord.memory_key)
            ).all()
            memories = [
                {
                    "category": record.category,
                    "key": record.memory_key,
                    "value": record.memory_value,
                    "confidence": record.confidence,
                }
                for record in records
            ]
        if query:
            query_terms = set(query.lower().split())
            memories.sort(
                key=lambda item: sum(
                    term in f"{item['key']} {item['value']}".lower()
                    for term in query_terms
                ),
                reverse=True,
            )
        if max_tokens is None:
            return memories
        selected: list[dict[str, Any]] = []
        used_tokens = 0
        for memory in memories:
            line = f"- [{memory['category']}] {memory['key']}: {memory['value']}"
            line_tokens = token_count(line)
            if selected and used_tokens + line_tokens > max_tokens:
                break
            selected.append(memory)
            used_tokens += line_tokens
        return selected

    def upsert_memory(
        self, user_id: str, memory: ExtractedMemory, source_session_id: str
    ) -> None:
        with self.session_factory() as db_session:
            record = db_session.scalar(
                select(UserMemoryRecord).where(
                    UserMemoryRecord.user_id == user_id,
                    UserMemoryRecord.category == memory.category,
                    UserMemoryRecord.memory_key == memory.key,
                )
            )
            if record is None:
                record = UserMemoryRecord(
                    user_id=user_id,
                    category=memory.category,
                    memory_key=memory.key,
                    updated_at=datetime.now(timezone.utc),
                )
                db_session.add(record)
            record.memory_value = memory.value
            record.confidence = max(0.0, min(1.0, memory.confidence))
            record.source_session_id = source_session_id
            record.is_active = memory.action != "delete"
            record.updated_at = datetime.now(timezone.utc)
            db_session.commit()

    def clear(self, user_id: str, session_id: str) -> None:
        with self._lock:
            self.get(user_id, session_id).clear()