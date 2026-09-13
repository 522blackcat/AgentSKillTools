"""Prompt definitions used by the memory workflows."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


def conversation_prompt(system_prompt: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                f"{system_prompt}\n\n"
                "Long-term user memory (across all windows):\n{long_term_memory}",
            ),
            MessagesPlaceholder("history"),
            ("human", "{input}"),
        ]
    )


def memory_extraction_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Extract stable user facts from the conversation turn. "
                "Ignore temporary requests, model guesses, and sensitive data. "
                "Return a JSON array only. Each item must contain: category, key, "
                "value, confidence (0 to 1), action (upsert or delete). "
                "Use categories profile, preference, goal, constraint, or fact. "
                "Return [] when there is no stable fact.",
            ),
            ("human", "User: {user_input}\nAssistant: {assistant_output}"),
        ]
    )


def summary_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Update the conversation summary. Preserve user preferences, "
                "decisions, IDs, unresolved issues, and important constraints. "
                "Return only the updated summary.",
            ),
            (
                "human",
                "Existing summary:\n{summary}\n\n"
                "New conversation:\n{transcript}",
            ),
        ]
    )


def account_manager_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are an account manager.\n"
                "Long-term user memory (across all windows):\n{long_term_memory}\n\n"
                "Current conversation summary (this window only):\n{summary}",
            ),
            MessagesPlaceholder("history"),
            ("human", "{input}"),
        ]
    )