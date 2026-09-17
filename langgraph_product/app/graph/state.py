"""Agent graph state."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    tenant_id: str
    user_id: str
    session_id: str | None
    run_id: str

    user_input: str
    normalized_input: str
    messages: list[dict[str, Any]]

    intent: str
    route: str
    risk_level: str
    token_budget: dict[str, Any]
    token_usage: dict[str, Any]
    model_provider: str
    model_provider_type: str
    model_id: str
    model_base_url: str
    model_api_key: str
    model_input_cost_per_1k: float
    model_output_cost_per_1k: float
    model_fallbacks: list[dict[str, Any]]

    memory_context: str
    memory_candidates: list[dict[str, Any]]
    knowledge_base_id: str | None
    rag_query: str
    rag_results: list[dict[str, Any]]
    rag_context: str

    tool_plan: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]

    review_required: bool
    review_request: dict[str, Any]
    review_decision: dict[str, Any]

    builder_request: dict[str, Any]
    builder_domain: str
    builder_product_name: str
    builder_domain_template: dict[str, Any]
    agent_blueprint: dict[str, Any]
    agent_artifacts: list[dict[str, Any]]
    generated_files: list[dict[str, Any]]
    validation_results: list[dict[str, Any]]

    final_answer: str
    errors: list[dict[str, Any]]
    trace: list[dict[str, Any]]
