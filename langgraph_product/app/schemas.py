"""API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    plan: str = "starter"


class TenantRead(BaseModel):
    id: str
    name: str
    plan: str
    status: str


class UserCreate(BaseModel):
    tenant_id: str
    email: str
    username: str = Field(min_length=1, max_length=120)
    display_name: str = ""
    role: str = "user"


class UserRead(BaseModel):
    id: str
    tenant_id: str
    email: str
    username: str
    role: str
    status: str


class SessionCreate(BaseModel):
    tenant_id: str
    user_id: str
    title: str = ""


class SessionRead(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    title: str
    status: str


class ChatRunCreate(BaseModel):
    tenant_id: str
    user_id: str
    session_id: str | None = None
    message: str = Field(min_length=1)
    graph_name: str = "main"
    knowledge_base_id: str | None = None


class BuilderRunCreate(BaseModel):
    tenant_id: str
    user_id: str
    domain: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    requirements: str = ""
    domain_template_id: str | None = None


class AgentRunRead(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    session_id: str | None
    graph_name: str
    status: str
    input_json: dict[str, Any]
    output_json: dict[str, Any]


class TokenGrantCreate(BaseModel):
    tenant_id: str
    user_id: str | None = None
    granted_tokens: int = Field(gt=0)
    reason: str = ""
    granted_by_user_id: str | None = None


class TokenUsageCreate(BaseModel):
    tenant_id: str
    user_id: str
    run_id: str | None = None
    node_name: str = ""
    call_type: str
    model_provider: str = ""
    model_id: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    embedding_tokens: int = 0
    rerank_tokens: int = 0
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ModelProviderCreate(BaseModel):
    name: str = Field(min_length=1)
    provider_type: str = "stub"
    base_url: str = ""
    status: str = "active"


class ModelRegistryCreate(BaseModel):
    provider_id: str
    model_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    context_window: int = Field(default=8192, gt=0)
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0
    supports_json_schema: bool = False
    supports_tools: bool = False
    status: str = "active"


class SecretCreate(BaseModel):
    tenant_id: str
    name: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1)
    created_by_user_id: str


class ToolCallCreate(BaseModel):
    tenant_id: str
    run_id: str | None = None
    tool_name: str = Field(min_length=1, max_length=160)
    risk_level: str = "low"
    status: str = "planned"
    input_summary: str = ""
    output_summary: str = ""
    error_json: dict[str, Any] | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class BackgroundJobCreate(BaseModel):
    tenant_id: str
    job_type: str = Field(min_length=1, max_length=120)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_by_user_id: str
    max_attempts: int = Field(default=3, ge=1, le=10)


class QuotaRead(BaseModel):
    tenant_id: str
    user_id: str | None
    token_limit: int
    token_used: int
    token_remaining: int


class ReviewDecisionCreate(BaseModel):
    tenant_id: str
    reviewer_user_id: str
    decision: str
    comment: str = ""
    revised_action: dict[str, Any] | None = None


class FeedbackCreate(BaseModel):
    tenant_id: str
    user_id: str
    run_id: str | None = None
    rating: int = Field(ge=-1, le=1)
    category: str = "general"
    comment: str = ""
    correction: dict[str, Any] = Field(default_factory=dict)


class DomainTemplateCreate(BaseModel):
    tenant_id: str | None = None
    domain: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = "1.0.0"
    compliance_profile: dict[str, Any] = Field(default_factory=dict)
    required_modules: list[str] = Field(default_factory=list)
    default_prompts: dict[str, Any] = Field(default_factory=dict)
    required_eval_cases: list[dict[str, Any]] = Field(default_factory=list)


class DomainTemplateStatusUpdate(BaseModel):
    tenant_id: str | None = None
    status: str = Field(pattern="^(active|deprecated|archived)$")


class DomainTemplateReviewDecision(BaseModel):
    tenant_id: str
    reviewer_user_id: str
    decision: str = Field(pattern="^(approve|reject)$")
    comment: str = ""


class ProjectSnapshotCreate(BaseModel):
    tenant_id: str
    owner_user_id: str
    name: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    blueprint: dict[str, Any] = Field(default_factory=dict)


class MemoryCreate(BaseModel):
    tenant_id: str
    user_id: str
    category: str = "preference"
    memory_key: str = Field(min_length=1)
    memory_value: str = Field(min_length=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_session_id: str | None = None


class KnowledgeBaseCreate(BaseModel):
    tenant_id: str
    name: str = Field(min_length=1)
    domain: str = "general"
    description: str = ""


class DocumentIngest(BaseModel):
    tenant_id: str
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_uri: str = ""
    doc_type: str = "text"
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchRequest(BaseModel):
    tenant_id: str
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    run_id: str | None = None
