"""Memory workflows and assistant services."""

from __future__ import annotations

from typing import Any, Callable

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables.utils import ConfigurableFieldSpec
from pydantic import PrivateAttr

from ..llm import model
from ..prompts import (
    account_manager_prompt,
    conversation_prompt,
    memory_extraction_prompt,
    summary_prompt,
)
from ..token_utils import ContextBudget, clip_text, token_count
from .models import ExtractedMemory
from .operator import DatabaseChatMessageHistory, DatabaseSessionHistoryStore


def _history_config() -> list[ConfigurableFieldSpec]:
    return [
        ConfigurableFieldSpec(
            id="user_id", annotation=str, name="User ID", description="Authenticated user ID"
        ),
        ConfigurableFieldSpec(
            id="session_id", annotation=str, name="Session ID", description="Chat window ID"
        ),
    ]


def _format_memories(memories: list[dict[str, Any]]) -> str:
    if not memories:
        return "(no long-term memory)"
    return "\n".join(
        f"- [{item['category']}] {item['key']}: {item['value']}"
        for item in memories
    )


def _submit_extraction(
    submitter: Callable[..., Any] | None,
    extractor: "UserMemoryExtractor",
    user_id: str,
    session_id: str,
    user_input: str,
    assistant_output: str,
) -> None:
    arguments = (user_id, session_id, user_input, assistant_output)
    if submitter is None:
        extractor.extract_and_save(*arguments)
    else:
        submitter(extractor.extract_and_save, *arguments)


class UserMemoryExtractor:
    def __init__(self, store: DatabaseSessionHistoryStore, extraction_model=model):
        self.store = store
        self._chain = (
            memory_extraction_prompt() | extraction_model | JsonOutputParser()
        )

    def extract_and_save(
        self,
        user_id: str,
        session_id: str,
        user_input: str,
        assistant_output: str,
    ) -> list[ExtractedMemory]:
        raw_items = self._chain.invoke(
            {"user_input": user_input, "assistant_output": assistant_output}
        )
        memories = [ExtractedMemory.model_validate(item) for item in raw_items]
        for memory in memories:
            if memory.confidence >= 0.75 and memory.key and memory.value:
                self.store.upsert_memory(user_id, memory, session_id)
        return memories


def _conversation_chain(system_prompt: str, chat_model=model):
    return conversation_prompt(system_prompt) | chat_model


class BufferMemoryAssistant:
    def __init__(
        self,
        store: DatabaseSessionHistoryStore | None = None,
        budget: ContextBudget | None = None,
        memory_submitter: Callable[..., Any] | None = None,
        chat_model=model,
    ):
        self.store = store or DatabaseSessionHistoryStore()
        self.budget = budget or ContextBudget()
        self.memory_submitter = memory_submitter
        self.memory_extractor = UserMemoryExtractor(self.store, chat_model)
        chain = _conversation_chain(
            "You are a customer support agent. Use the complete conversation "
            "history to give consistent, accurate answers. Never invent order data.",
            chat_model,
        )
        self._chain = RunnableWithMessageHistory(
            chain,
            lambda user_id, session_id: self.store.get(
                user_id, session_id, self.budget.recent_message_tokens
            ),
            input_messages_key="input",
            history_messages_key="history",
            history_factory_config=_history_config(),
        )

    def ask(self, user_id: str, session_id: str, user_input: str) -> str:
        result = self._chain.invoke(
            {
                "input": user_input,
                "long_term_memory": _format_memories(
                    self.store.list_memories(
                        user_id, user_input, self.budget.long_term_tokens
                    )
                ),
            },
            config={"configurable": {"user_id": user_id, "session_id": session_id}},
        )
        _submit_extraction(
            self.memory_submitter,
            self.memory_extractor,
            user_id,
            session_id,
            user_input,
            str(result),
        )
        return str(result)


class WindowMemoryAssistant(BufferMemoryAssistant):
    def __init__(self, window_size: int = 10, **kwargs: Any):
        if window_size < 2 or window_size % 2:
            raise ValueError("window_size must be an even number >= 2")
        self.window_size = window_size
        super().__init__(**kwargs)


class SummaryChatMessageHistory(DatabaseChatMessageHistory):
    _summary_model: Any = PrivateAttr()
    _recent_messages: int = PrivateAttr()
    _summarize_after: int = PrivateAttr()
    _compaction_trigger_tokens: int = PrivateAttr()
    _summary_max_tokens: int = PrivateAttr()

    def __init__(
        self,
        session_factory,
        user_id,
        session_id,
        summary_model,
        recent_messages=4,
        summarize_after=8,
        max_prompt_tokens: int | None = None,
        compaction_trigger_tokens=8000,
        summary_max_tokens=1200,
    ):
        super().__init__(session_factory, user_id, session_id, max_prompt_tokens)
        self._summary_model = summary_model
        self._recent_messages = recent_messages
        self._summarize_after = summarize_after
        self._compaction_trigger_tokens = compaction_trigger_tokens
        self._summary_max_tokens = summary_max_tokens

    def compact(self) -> None:
        if len(self._messages) <= self._recent_messages:
            return
        history_text = "\n".join(
            f"{message.type}: {message.content}" for message in self._messages
        )
        if (
            len(self._messages) <= self._summarize_after
            and token_count(history_text) <= self._compaction_trigger_tokens
        ):
            return
        old_messages = self._messages[:-self._recent_messages]
        transcript = clip_text(
            "\n".join(f"{message.type}: {message.content}" for message in old_messages),
            4000,
        )
        summary = self._summary_model.invoke(
            summary_prompt().format(
                summary=self._summary or "(none)", transcript=transcript
            )
        )
        self._summary = clip_text(str(summary).strip(), self._summary_max_tokens)
        self._messages = self._messages[-self._recent_messages :]
        self._save()


class SummaryMemoryAssistant:
    def __init__(
        self,
        store: DatabaseSessionHistoryStore | None = None,
        budget: ContextBudget | None = None,
        memory_submitter: Callable[..., Any] | None = None,
        chat_model=model,
    ):
        self.store = store or DatabaseSessionHistoryStore()
        self.budget = budget or ContextBudget()
        self.memory_submitter = memory_submitter
        self.memory_extractor = UserMemoryExtractor(self.store, chat_model)
        self.chat_model = chat_model

    def ask(self, user_id: str, session_id: str, user_input: str) -> str:
        history = SummaryChatMessageHistory(
            self.store.session_factory,
            user_id,
            session_id,
            self.chat_model,
            max_prompt_tokens=self.budget.recent_message_tokens,
            compaction_trigger_tokens=self.budget.compaction_trigger_tokens,
            summary_max_tokens=self.budget.summary_tokens,
        )
        result = (account_manager_prompt() | self.chat_model).invoke(
            {
                "long_term_memory": _format_memories(
                    self.store.list_memories(
                        user_id, user_input, self.budget.long_term_tokens
                    )
                ),
                "summary": clip_text(
                    history.summary or "(no previous summary)",
                    self.budget.summary_tokens,
                ),
                "history": history.messages,
                "input": user_input,
            }
        )
        history.add_messages(
            [HumanMessage(content=user_input), AIMessage(content=str(result))]
        )
        history.compact()
        _submit_extraction(
            self.memory_submitter,
            self.memory_extractor,
            user_id,
            session_id,
            user_input,
            str(result),
        )
        return str(result)
