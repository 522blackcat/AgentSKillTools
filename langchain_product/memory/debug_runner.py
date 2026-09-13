"""Interactive entry point for inspecting memory routing decisions.

Run with:
    python -m langchain_product.memory.debug_runner
"""

from __future__ import annotations

from dataclasses import dataclass

from ..token_utils import ContextBudget, token_count
from .operator import DatabaseSessionHistoryStore
from .service import (
    BufferMemoryAssistant,
    SummaryMemoryAssistant,
    UserMemoryExtractor,
)


@dataclass(frozen=True)
class MemoryRoute:
    name: str
    reason: str
    history_tokens: int
    long_term_memory_count: int


class DebugMemoryAssistant:
    """Route each request to short-term or summary memory for debugging."""

    def __init__(
        self,
        store: DatabaseSessionHistoryStore | None = None,
        budget: ContextBudget | None = None,
    ):
        self.store = store or DatabaseSessionHistoryStore()
        self.budget = budget or ContextBudget()
        self.short_term = BufferMemoryAssistant(
            store=self.store,
            budget=self.budget,
        )
        self.medium_term = SummaryMemoryAssistant(
            store=self.store,
            budget=self.budget,
        )

    def choose_route(
        self, user_id: str, session_id: str, user_input: str
    ) -> MemoryRoute:
        history = self.store.get(user_id, session_id)
        history_text = "\n".join(
            f"{message.type}: {message.content}" for message in history._messages
        )
        history_tokens = token_count(history_text)
        memories = self.store.list_memories(
            user_id, user_input, self.budget.long_term_tokens
        )
        if history_tokens >= self.budget.compaction_trigger_tokens:
            return MemoryRoute(
                name="medium-term-summary",
                reason=(
                    "完整历史已达到摘要触发阈值，使用当前会话摘要 + 最近消息"
                ),
                history_tokens=history_tokens,
                long_term_memory_count=len(memories),
            )
        return MemoryRoute(
            name="short-term-recent-messages",
            reason="完整历史低于摘要触发阈值，使用最近消息",
            history_tokens=history_tokens,
            long_term_memory_count=len(memories),
        )

    def ask(self, user_id: str, session_id: str, user_input: str) -> str:
        route = self.choose_route(user_id, session_id, user_input)
        print(
            f"[memory-route] {route.name}; "
            f"history_tokens={route.history_tokens}; "
            f"long_term_memories={route.long_term_memory_count}"
        )
        print(f"[memory-reason] {route.reason}")
        if route.name == "medium-term-summary":
            return self.medium_term.ask(user_id, session_id, user_input)
        return self.short_term.ask(user_id, session_id, user_input)


def main() -> None:
    assistant = DebugMemoryAssistant()
    user_id = input("user_id [debug-user]: ").strip() or "debug-user"
    session_id = input("session_id [new]: ").strip()
    if not session_id:
        session_id = assistant.store.create_window(user_id)
        print(f"[new-window] session_id={session_id}")
    print("输入 exit 退出。")
    while True:
        user_input = input("你: ").strip()
        if user_input.lower() == "exit":
            break
        if not user_input:
            continue
        print(f"助手: {assistant.ask(user_id, session_id, user_input)}")


if __name__ == "__main__":
    main()