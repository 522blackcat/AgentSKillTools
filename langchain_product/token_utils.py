"""Token counting, clipping, and context budget utilities."""

from __future__ import annotations

from dataclasses import dataclass

import tiktoken


@dataclass(frozen=True)
class ContextBudget:
    """Token budget for context sent to the answering model."""

    max_context_tokens: int = 12000
    reserved_output_tokens: int = 2000
    system_prompt_tokens: int = 800
    user_input_tokens: int = 800
    safety_margin_tokens: int = 400
    long_term_tokens: int = 800
    summary_tokens: int = 1200
    recent_message_tokens: int = 6000
    compaction_trigger_tokens: int = 8000

    def __post_init__(self) -> None:
        reserved_context = (
            self.reserved_output_tokens
            + self.system_prompt_tokens
            + self.user_input_tokens
            + self.safety_margin_tokens
            + self.long_term_tokens
            + self.summary_tokens
            + self.recent_message_tokens
        )
        budgets = (
            self.max_context_tokens,
            self.reserved_output_tokens,
            self.system_prompt_tokens,
            self.user_input_tokens,
            self.safety_margin_tokens,
            self.long_term_tokens,
            self.summary_tokens,
            self.recent_message_tokens,
            self.compaction_trigger_tokens,
        )
        if min(budgets) < 0:
            raise ValueError("context token budgets must not be negative")
        if reserved_context > self.max_context_tokens:
            raise ValueError(
                "reserved output and memory budgets exceed max_context_tokens"
            )
        if self.compaction_trigger_tokens >= self.max_context_tokens:
            raise ValueError("compaction trigger must be below max_context_tokens")

    @property
    def input_tokens(self) -> int:
        return self.max_context_tokens - self.reserved_output_tokens


_TOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")


def token_count(text: str) -> int:
    return len(_TOKEN_ENCODER.encode(text, disallowed_special=()))


def clip_text(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    token_ids = _TOKEN_ENCODER.encode(text, disallowed_special=())
    if len(token_ids) <= max_tokens:
        return text
    suffix = "..."
    suffix_tokens = len(_TOKEN_ENCODER.encode(suffix))
    content_tokens = max(0, max_tokens - suffix_tokens)
    return _TOKEN_ENCODER.decode(token_ids[:content_tokens]).rstrip() + suffix