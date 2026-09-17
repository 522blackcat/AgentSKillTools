"""Shared agent state contract."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    tenant_id: str
    user_id: str
    session_id: str
    knowledge_base_id: str
    user_input: str
    route: str
    chunks: list[dict[str, Any]]
    memory_context: dict[str, Any]
    tool_plan: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    answer: str
    citations: list[dict[str, Any]]
    risk_level: str
    review_required: bool
    audit_nodes: list[str]
