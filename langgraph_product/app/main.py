"""FastAPI 入口。

这个文件负责 API 编排：认证、RBAC、参数校验和调用 service/runtime。
真正的生成链路主要在 app/runtime.py、app/graph/nodes.py 和 app/builder/。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import Generator
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session


from app.auth import authenticate_api_token, issue_api_token, verify_admin_secret
from app.database.models import AgentRun, User
from app.database.session import SessionLocal, engine, get_db, init_db
from app.idempotency import get_idempotent_response, save_idempotent_response
from app.knowledge.service import create_knowledge_base, ingest_document, search_knowledge_base
from app.memory.service import create_memory, search_memories
from app.memory.service import load_memory_context, load_recent_messages
from app.runtime import invoke_agent_run
from app.schemas import (
    AgentRunRead,
    BackgroundJobCreate,
    BuilderRunCreate,
    ChatRunCreate,
    DomainTemplateCreate,
    DomainTemplateReviewDecision,
    DocumentIngest,
    FeedbackCreate,
    KnowledgeBaseCreate,
    KnowledgeSearchRequest,
    MemoryCreate,
    ModelProviderCreate,
    ModelRegistryCreate,
    ProjectSnapshotCreate,
    QuotaRead,
    ReviewDecisionCreate,
    SecretCreate,
    SessionCreate,
    SessionRead,
    TenantCreate,
    TenantRead,
    DomainTemplateStatusUpdate,
    ToolCallCreate,
    TokenGrantCreate,
    TokenUsageCreate,
    UserCreate,
    UserRead,
)
from app.jobs import create_background_job, get_background_job, list_background_jobs, rq_settings
from app.secrets import create_secret, list_secrets
from app.tooling import list_tool_calls, record_tool_call
from app.services import (
    create_builder_run,
    create_chat_run,
    create_domain_template,
    create_feedback,
    create_model_provider,
    create_model_registry_entry,
    create_project_from_schema,
    create_session,
    create_tenant,
    create_user,
    decide_domain_template_review,
    decide_review,
    ensure_default_domain_templates,
    ensure_default_model_registry,
    get_domain_template as get_domain_template_service,
    grant_tokens,
    list_domain_templates,
    list_model_providers,
    list_model_registry,
    list_pending_domain_templates,
    list_project_eval_reports,
    list_project_validations,
    list_project_versions,
    list_run_events,
    pending_reviews,
    read_quota,
    record_token_usage,
    repair_project,
    rollback_project,
    suggest_domain_template_improvements,
    update_domain_template_status,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> Generator[None, None, None]:
    init_db()
    with SessionLocal() as db:
        ensure_default_domain_templates(db)
        ensure_default_model_registry(db)
    yield


app = FastAPI(
    title="LangGraph Product Agent Platform",
    version="0.1.0",
    lifespan=lifespan,
)
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="ui")


def current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> User:
    try:
        return authenticate_api_token(db, authorization)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_roles(user: User, roles: set[str]) -> None:
    if user.role not in roles:
        raise HTTPException(status_code=403, detail="insufficient role")


def require_tenant(user: User, tenant_id: str | None) -> None:
    if tenant_id is not None and user.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="tenant mismatch")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("select 1"))
    return {"status": "ready", "database": "ok"}


@app.post("/v1/tenants", response_model=TenantRead)
def create_tenant_endpoint(data: TenantCreate, db: Session = Depends(get_db)) -> Any:
    return create_tenant(db, data)


@app.post("/v1/users", response_model=UserRead)
def create_user_endpoint(data: UserCreate, db: Session = Depends(get_db)) -> Any:
    return create_user(db, data)


@app.post("/v1/users/{user_id}/api-token")
def create_user_api_token(
    user_id: str,
    tenant_id: str = Query(...),
    x_admin_secret: str | None = Header(default=None, alias="X-Admin-Secret"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        verify_admin_secret(x_admin_secret)
        user, token = issue_api_token(db, tenant_id, user_id)
    except ValueError as exc:
        status_code = 401 if "secret" in str(exc) else 404
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return {
        "tenant_id": user.tenant_id,
        "user_id": user.id,
        "token_type": "bearer",
        "api_token": token,
    }


@app.get("/v1/auth/whoami", response_model=UserRead)
def auth_whoami(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> Any:
    try:
        return authenticate_api_token(db, authorization)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.post("/v1/sessions", response_model=SessionRead)
def create_session_endpoint(data: SessionCreate, db: Session = Depends(get_db)) -> Any:
    return create_session(db, data.tenant_id, data.user_id, data.title)


@app.post("/v1/chat/runs", response_model=AgentRunRead)
def create_chat_run_endpoint(
    data: ChatRunCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> Any:
    payload = data.model_dump_json()
    existing = get_idempotent_response(
        db,
        data.tenant_id,
        data.user_id,
        idempotency_key,
        payload,
    )
    if existing is not None:
        return existing
    run = create_chat_run(db, data)
    response = _run_response(run)
    save_idempotent_response(db, data.tenant_id, data.user_id, idempotency_key, payload, response)
    return response


@app.post("/v1/builder/runs", response_model=AgentRunRead)
def create_builder_run_endpoint(
    data: BuilderRunCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> Any:
    payload = data.model_dump_json()
    existing = get_idempotent_response(
        db,
        data.tenant_id,
        data.user_id,
        idempotency_key,
        payload,
    )
    if existing is not None:
        return existing
    run = create_builder_run(db, data)
    response = _run_response(run)
    save_idempotent_response(db, data.tenant_id, data.user_id, idempotency_key, payload, response)
    return response


@app.get("/v1/chat/runs/{run_id}", response_model=AgentRunRead)
def get_run(run_id: str, tenant_id: str = Query(...), db: Session = Depends(get_db)) -> Any:
    run = db.get(AgentRun, run_id)
    if run is None or run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.post("/v1/chat/runs/{run_id}/invoke", response_model=AgentRunRead)
def invoke_run(run_id: str, tenant_id: str = Query(...), db: Session = Depends(get_db)) -> Any:
    run = db.get(AgentRun, run_id)
    if run is None or run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="run not found")
    try:
        return invoke_agent_run(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/builder/runs/{run_id}/invoke", response_model=AgentRunRead)
def invoke_builder_run(
    run_id: str,
    tenant_id: str = Query(...),
    db: Session = Depends(get_db),
) -> Any:
    return invoke_run(run_id=run_id, tenant_id=tenant_id, db=db)


@app.get("/v1/reviews/pending")
def get_pending_reviews(
    tenant_id: str = Query(...),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return [
        {
            "id": review.id,
            "tenant_id": review.tenant_id,
            "run_id": review.run_id,
            "requester_user_id": review.requester_user_id,
            "risk_level": review.risk_level,
            "reason": review.reason,
            "proposed_action": review.proposed_action,
            "evidence": review.evidence,
            "status": review.status,
            "created_at": review.created_at.isoformat(),
        }
        for review in pending_reviews(db, tenant_id)
    ]


@app.post("/v1/reviews/{review_id}/decide")
def post_review_decision(
    review_id: str,
    data: ReviewDecisionCreate,
    auth_user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_tenant(auth_user, data.tenant_id)
    if auth_user.id != data.reviewer_user_id:
        raise HTTPException(status_code=403, detail="reviewer token mismatch")
    reviewer = db.get(User, data.reviewer_user_id)
    if reviewer is None or reviewer.tenant_id != data.tenant_id:
        raise HTTPException(status_code=404, detail="reviewer not found")
    if reviewer.role not in {"reviewer", "admin", "owner"}:
        raise HTTPException(status_code=403, detail="reviewer role required")
    try:
        review, decision, run = decide_review(db, review_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "review_id": review.id,
        "decision_id": decision.id,
        "status": review.status,
        "run_id": run.id,
        "run_status": run.status,
    }


@app.get("/v1/chat/runs/{run_id}/events")
def get_run_events(run_id: str, tenant_id: str = Query(...), db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "id": event.id,
            "node_name": event.node_name,
            "event_type": event.event_type,
            "payload": event.payload,
            "ok": event.ok,
            "created_at": event.created_at.isoformat(),
        }
        for event in list_run_events(db, tenant_id, run_id)
    ]


@app.get("/v1/chat/runs/{run_id}/stream")
def stream_run_events(run_id: str, tenant_id: str = Query(...), db: Session = Depends(get_db)) -> StreamingResponse:
    events = list_run_events(db, tenant_id, run_id)

    def body() -> Generator[str, None, None]:
        for event in events:
            yield f"id: {event.id}\n"
            yield f"event: {event.event_type}\n"
            yield f"data: {event.payload}\n\n"

    return StreamingResponse(body(), media_type="text/event-stream")


@app.get("/v1/quotas", response_model=QuotaRead)
def get_quota(
    tenant_id: str = Query(...),
    user_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return read_quota(db, tenant_id, user_id)


@app.post("/v1/quotas/grants")
def create_token_grant(data: TokenGrantCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    # Backward-compatible direct service remains available internally; public API is RBAC-protected.
    raise HTTPException(status_code=410, detail="use /v1/secure/quotas/grants")


@app.post("/v1/secure/quotas/grants")
def create_secure_token_grant(
    data: TokenGrantCreate,
    auth_user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_roles(auth_user, {"admin", "owner"})
    require_tenant(auth_user, data.tenant_id)
    grant = grant_tokens(db, data)
    return {
        "id": grant.id,
        "tenant_id": grant.tenant_id,
        "user_id": grant.user_id,
        "remaining_tokens": grant.remaining_tokens,
    }


@app.post("/v1/token-usage")
def create_token_usage(data: TokenUsageCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    event = record_token_usage(db, data)
    return {"id": event.id, "total_tokens": event.total_tokens}


@app.get("/v1/token-usage/runs/{run_id}")
def get_run_token_usage(
    run_id: str,
    tenant_id: str = Query(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = db.execute(
        text(
            "select coalesce(sum(total_tokens), 0) from token_usage_events "
            "where tenant_id = :tenant_id and run_id = :run_id"
        ),
        {"tenant_id": tenant_id, "run_id": run_id},
    )
    return {"run_id": run_id, "total_tokens": int(rows.scalar() or 0)}


@app.post("/v1/model-providers")
def post_model_provider(
    data: ModelProviderCreate,
    auth_user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_roles(auth_user, {"admin", "owner"})
    provider = create_model_provider(db, data)
    return {
        "id": provider.id,
        "name": provider.name,
        "provider_type": provider.provider_type,
        "base_url": provider.base_url,
        "status": provider.status,
    }


@app.get("/v1/model-providers")
def get_model_providers(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [
        {
            "id": provider.id,
            "name": provider.name,
            "provider_type": provider.provider_type,
            "base_url": provider.base_url,
            "status": provider.status,
        }
        for provider in list_model_providers(db)
    ]


@app.post("/v1/model-registry")
def post_model_registry(
    data: ModelRegistryCreate,
    auth_user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_roles(auth_user, {"admin", "owner"})
    try:
        model = create_model_registry_entry(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": model.id,
        "provider_id": model.provider_id,
        "model_id": model.model_id,
        "role": model.role,
        "context_window": model.context_window,
        "status": model.status,
    }


@app.get("/v1/model-registry")
def get_model_registry(
    role: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return [
        {
            "id": model.id,
            "provider_id": provider.id,
            "provider_name": provider.name,
            "provider_type": provider.provider_type,
            "model_id": model.model_id,
            "role": model.role,
            "context_window": model.context_window,
            "input_cost_per_1k": float(model.input_cost_per_1k),
            "output_cost_per_1k": float(model.output_cost_per_1k),
            "supports_json_schema": model.supports_json_schema,
            "supports_tools": model.supports_tools,
            "status": model.status,
        }
        for model, provider in list_model_registry(db, role)
    ]


@app.post("/v1/secrets")
def post_secret(
    data: SecretCreate,
    auth_user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_roles(auth_user, {"admin", "owner"})
    require_tenant(auth_user, data.tenant_id)
    if auth_user.id != data.created_by_user_id:
        raise HTTPException(status_code=403, detail="creator token mismatch")
    record = create_secret(db, data)
    return {
        "id": record.id,
        "tenant_id": record.tenant_id,
        "name": record.name,
        "version": record.version,
        "status": record.status,
        "value_sha256": record.value_sha256,
    }


@app.get("/v1/secrets")
def get_secrets(
    tenant_id: str = Query(...),
    auth_user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    require_roles(auth_user, {"admin", "owner"})
    require_tenant(auth_user, tenant_id)
    return [
        {
            "id": record.id,
            "tenant_id": record.tenant_id,
            "name": record.name,
            "version": record.version,
            "status": record.status,
            "value_sha256": record.value_sha256,
            "created_at": record.created_at.isoformat(),
        }
        for record in list_secrets(db, tenant_id)
    ]


@app.post("/v1/tool-calls")
def post_tool_call(
    data: ToolCallCreate,
    auth_user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_roles(auth_user, {"admin", "owner", "reviewer"})
    require_tenant(auth_user, data.tenant_id)
    call = record_tool_call(db, data)
    return {
        "id": call.id,
        "tenant_id": call.tenant_id,
        "run_id": call.run_id,
        "tool_name": call.tool_name,
        "risk_level": call.risk_level,
        "status": call.status,
        "started_at": call.started_at.isoformat() if call.started_at else None,
        "finished_at": call.finished_at.isoformat() if call.finished_at else None,
    }


@app.get("/v1/tool-calls")
def get_tool_calls(
    tenant_id: str = Query(...),
    run_id: str | None = Query(default=None),
    auth_user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    require_roles(auth_user, {"admin", "owner", "reviewer"})
    require_tenant(auth_user, tenant_id)
    return [
        {
            "id": call.id,
            "tenant_id": call.tenant_id,
            "run_id": call.run_id,
            "tool_name": call.tool_name,
            "risk_level": call.risk_level,
            "status": call.status,
            "input_summary": call.input_summary,
            "output_summary": call.output_summary,
            "error_json": call.error_json,
            "metadata_json": call.metadata_json,
            "created_at": call.created_at.isoformat(),
        }
        for call in list_tool_calls(db, tenant_id, run_id)
    ]


@app.post("/v1/jobs")
def post_background_job(
    data: BackgroundJobCreate,
    auth_user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_roles(auth_user, {"admin", "owner"})
    require_tenant(auth_user, data.tenant_id)
    if auth_user.id != data.created_by_user_id:
        raise HTTPException(status_code=403, detail="creator token mismatch")
    job = create_background_job(db, data)
    return {
        "id": job.id,
        "tenant_id": job.tenant_id,
        "job_type": job.job_type,
        "status": job.status,
        "rq": rq_settings(),
    }


@app.get("/v1/jobs")
def get_background_jobs(
    tenant_id: str = Query(...),
    auth_user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    require_roles(auth_user, {"admin", "owner"})
    require_tenant(auth_user, tenant_id)
    return [
        {
            "id": job.id,
            "tenant_id": job.tenant_id,
            "job_type": job.job_type,
            "status": job.status,
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
            "created_at": job.created_at.isoformat(),
        }
        for job in list_background_jobs(db, tenant_id)
    ]


@app.get("/v1/jobs/{job_id}")
def get_background_job_detail(
    job_id: str,
    tenant_id: str = Query(...),
    auth_user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_roles(auth_user, {"admin", "owner"})
    require_tenant(auth_user, tenant_id)
    try:
        job = get_background_job(db, tenant_id, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": job.id,
        "tenant_id": job.tenant_id,
        "job_type": job.job_type,
        "status": job.status,
        "payload": job.payload,
        "result": job.result,
        "error_json": job.error_json,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
    }


@app.post("/v1/memories")
def post_memory(data: MemoryCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    memory = create_memory(db, data)
    return {
        "id": memory.id,
        "category": memory.category,
        "key": memory.memory_key,
        "value": memory.memory_value,
    }


@app.get("/v1/memories/search")
def get_memory_search(
    tenant_id: str = Query(...),
    user_id: str = Query(...),
    query: str = Query(...),
    top_k: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return search_memories(db, tenant_id, user_id, query, top_k)


@app.get("/v1/sessions/{session_id}/memory-context")
def get_session_memory_context(
    session_id: str,
    tenant_id: str = Query(...),
    user_id: str = Query(...),
    query: str = Query(default=""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    context = load_memory_context(db, tenant_id, user_id, session_id, query)
    return {
        "summary": context.summary,
        "recent_messages": context.recent_messages,
        "long_term_memories": context.long_term_memories,
        "prompt_context": context.to_prompt_context(),
    }


@app.get("/v1/sessions/{session_id}/messages")
def get_session_messages(
    session_id: str,
    tenant_id: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return load_recent_messages(db, tenant_id, session_id, limit)


@app.post("/v1/knowledge-bases")
def post_knowledge_base(data: KnowledgeBaseCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    kb = create_knowledge_base(db, data)
    return {"id": kb.id, "tenant_id": kb.tenant_id, "name": kb.name, "domain": kb.domain}


@app.post("/v1/knowledge-bases/{kb_id}/documents")
def post_document(kb_id: str, data: DocumentIngest, db: Session = Depends(get_db)) -> dict[str, Any]:
    return ingest_document(db, kb_id, data)


@app.post("/v1/knowledge-bases/{kb_id}/search")
def post_knowledge_search(
    kb_id: str,
    data: KnowledgeSearchRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return search_knowledge_base(db, kb_id, data)


@app.post("/v1/generated-projects")
def create_generated_project(data: ProjectSnapshotCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    project = create_project_from_schema(db, data)
    return {
        "id": project.id,
        "tenant_id": project.tenant_id,
        "name": project.name,
        "domain": project.domain,
        "active_version_id": project.active_version_id,
    }


@app.get("/v1/generated-projects/{project_id}/versions")
def get_project_versions(
    project_id: str,
    tenant_id: str = Query(...),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return [
        {
            "id": version.id,
            "version_number": version.version_number,
            "status": version.status,
            "diff_summary": version.diff_summary,
            "created_at": version.created_at.isoformat(),
        }
        for version in list_project_versions(db, tenant_id, project_id)
    ]


@app.get("/v1/generated-projects/{project_id}/validations")
def get_project_validations(
    project_id: str,
    tenant_id: str = Query(...),
    version_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return [
        {
            "id": validation.id,
            "project_id": validation.project_id,
            "version_id": validation.version_id,
            "status": validation.status,
            "summary": validation.summary,
            "checks": validation.checks,
            "created_at": validation.created_at.isoformat(),
        }
        for validation in list_project_validations(db, tenant_id, project_id, version_id)
    ]


@app.get("/v1/generated-projects/{project_id}/eval-reports")
def get_project_eval_reports(
    project_id: str,
    tenant_id: str = Query(...),
    version_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return [
        {
            "id": report.id,
            "project_id": report.project_id,
            "version_id": report.version_id,
            "status": report.status,
            "score": float(report.score),
            "summary": report.summary,
            "checks": report.checks,
            "created_at": report.created_at.isoformat(),
        }
        for report in list_project_eval_reports(db, tenant_id, project_id, version_id)
    ]


@app.post("/v1/generated-projects/{project_id}/versions/{version_id}/rollback")
def rollback_project_version(
    project_id: str,
    version_id: str,
    tenant_id: str = Query(...),
    auth_user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_roles(auth_user, {"admin", "owner"})
    require_tenant(auth_user, tenant_id)
    try:
        project = rollback_project(db, tenant_id, project_id, version_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": project.id, "active_version_id": project.active_version_id}


@app.post("/v1/generated-projects/{project_id}/repair")
def repair_generated_project(
    project_id: str,
    tenant_id: str = Query(...),
    force: bool = Query(default=False),
    auth_user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_roles(auth_user, {"admin", "owner"})
    require_tenant(auth_user, tenant_id)
    try:
        return repair_project(db, tenant_id, project_id, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/v1/domain-templates")
def get_domain_templates(
    tenant_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return [
        {
            "id": template.id,
            "tenant_id": template.tenant_id,
            "domain": template.domain,
            "name": template.name,
            "version": template.version,
            "required_modules": template.required_modules,
            "status": template.status,
        }
        for template in list_domain_templates(db, tenant_id)
    ]


@app.post("/v1/domain-templates/defaults/seed")
def seed_default_domain_templates(db: Session = Depends(get_db)) -> dict[str, str]:
    ensure_default_domain_templates(db)
    return {"status": "seeded"}


@app.get("/v1/domain-templates/pending")
def get_pending_domain_templates(
    tenant_id: str = Query(...),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return [
        {
            "id": template.id,
            "tenant_id": template.tenant_id,
            "domain": template.domain,
            "name": template.name,
            "version": template.version,
            "required_modules": template.required_modules,
            "status": template.status,
        }
        for template in list_pending_domain_templates(db, tenant_id)
    ]


@app.get("/v1/domain-templates/{template_id}")
def get_domain_template(
    template_id: str,
    tenant_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        template = get_domain_template_service(db, template_id, tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": template.id,
        "tenant_id": template.tenant_id,
        "domain": template.domain,
        "name": template.name,
        "version": template.version,
        "compliance_profile": template.compliance_profile,
        "required_modules": template.required_modules,
        "default_prompts": template.default_prompts,
        "required_eval_cases": template.required_eval_cases,
        "status": template.status,
    }


@app.patch("/v1/domain-templates/{template_id}/status")
def patch_domain_template_status(
    template_id: str,
    data: DomainTemplateStatusUpdate,
    auth_user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_roles(auth_user, {"admin", "owner"})
    require_tenant(auth_user, data.tenant_id)
    try:
        template = update_domain_template_status(db, template_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": template.id, "status": template.status}


@app.post("/v1/domain-templates/{template_id}/review")
def post_domain_template_review(
    template_id: str,
    data: DomainTemplateReviewDecision,
    auth_user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_roles(auth_user, {"admin", "owner"})
    require_tenant(auth_user, data.tenant_id)
    if auth_user.id != data.reviewer_user_id:
        raise HTTPException(status_code=403, detail="reviewer token mismatch")
    reviewer = db.get(User, data.reviewer_user_id)
    if reviewer is None or reviewer.tenant_id != data.tenant_id:
        raise HTTPException(status_code=404, detail="reviewer not found")
    if reviewer.role not in {"admin", "owner"}:
        raise HTTPException(status_code=403, detail="owner or admin role required")
    try:
        template = decide_domain_template_review(db, template_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": template.id, "status": template.status, "decision": data.decision}


@app.get("/v1/domain-templates/{template_id}/improvement-suggestions")
def get_domain_template_improvement_suggestions(
    template_id: str,
    tenant_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return suggest_domain_template_improvements(db, template_id, tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/domain-templates")
def post_domain_template(data: DomainTemplateCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    template = create_domain_template(db, data)
    return {
        "id": template.id,
        "domain": template.domain,
        "name": template.name,
        "version": template.version,
        "status": template.status,
    }


@app.post("/v1/feedback")
def post_feedback(data: FeedbackCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = create_feedback(db, data)
    return {"id": item.id, "rating": item.rating, "category": item.category}


def _run_response(run: AgentRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "tenant_id": run.tenant_id,
        "user_id": run.user_id,
        "session_id": run.session_id,
        "graph_name": run.graph_name,
        "status": run.status,
        "input_json": run.input_json,
        "output_json": run.output_json,
    }
