"""Small service layer for phase-one platform operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.builder.evals import evaluate_generated_project
from app.builder.project_writer import write_generated_project
from app.builder.validator import validate_generated_project
from app.database.models import (
    AgentEvent,
    AgentRun,
    ChatSession,
    DomainTemplate,
    FeedbackItem,
    GeneratedProject,
    GraphCheckpoint,
    GraphThread,
    HumanReviewDecision,
    HumanReviewRequest,
    ModelProvider,
    ModelRegistry,
    ProjectVersion,
    ProjectEvalReport,
    ProjectValidation,
    Tenant,
    TokenGrant,
    TokenQuota,
    TokenUsageEvent,
    User,
)
from app.domain_templates import DEFAULT_DOMAIN_TEMPLATES
from app.memory.service import save_turn
from app.schemas import BuilderRunCreate, ChatRunCreate, DomainTemplateCreate, DomainTemplateReviewDecision
from app.schemas import DomainTemplateStatusUpdate, FeedbackCreate, ModelProviderCreate
from app.schemas import ModelRegistryCreate, ProjectSnapshotCreate, ReviewDecisionCreate
from app.schemas import TenantCreate, TokenGrantCreate, TokenUsageCreate
from app.schemas import UserCreate


def create_tenant(db: Session, data: TenantCreate) -> Tenant:
    tenant = Tenant(name=data.name, plan=data.plan)
    db.add(tenant)
    db.flush()
    quota = TokenQuota(
        tenant_id=tenant.id,
        user_id=None,
        quota_type="monthly",
        token_limit=settings.default_monthly_token_limit,
        token_used=0,
    )
    db.add(quota)
    db.commit()
    db.refresh(tenant)
    return tenant


def create_user(db: Session, data: UserCreate) -> User:
    user = User(
        tenant_id=data.tenant_id,
        email=data.email,
        username=data.username,
        display_name=data.display_name,
        role=data.role,
    )
    db.add(user)
    db.flush()
    quota = TokenQuota(
        tenant_id=data.tenant_id,
        user_id=user.id,
        quota_type="daily",
        token_limit=settings.default_daily_token_limit,
        token_used=0,
        reset_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db.add(quota)
    db.commit()
    db.refresh(user)
    return user


def create_session(db: Session, tenant_id: str, user_id: str, title: str) -> ChatSession:
    session = ChatSession(tenant_id=tenant_id, user_id=user_id, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def create_chat_run(db: Session, data: ChatRunCreate) -> AgentRun:
    run = AgentRun(
        tenant_id=data.tenant_id,
        user_id=data.user_id,
        session_id=data.session_id,
        graph_name=data.graph_name,
        input_json={"message": data.message, "knowledge_base_id": data.knowledge_base_id},
        output_json={},
        status="created",
    )
    db.add(run)
    db.flush()
    db.add(
        AgentEvent(
            tenant_id=data.tenant_id,
            run_id=run.id,
            node_name="api",
            event_type="run.created",
            payload={"graph_name": data.graph_name},
        )
    )
    db.commit()
    db.refresh(run)
    return run


def create_builder_run(db: Session, data: BuilderRunCreate) -> AgentRun:
    payload = {
        "domain": data.domain,
        "product_name": data.product_name,
        "requirements": data.requirements,
        "domain_template_id": data.domain_template_id,
    }
    run = AgentRun(
        tenant_id=data.tenant_id,
        user_id=data.user_id,
        graph_name="agent_builder",
        input_json=payload,
        output_json={"status": "blueprint_pending"},
        status="created",
    )
    db.add(run)
    db.flush()
    db.add(
        AgentEvent(
            tenant_id=data.tenant_id,
            run_id=run.id,
            node_name="api",
            event_type="builder.run.created",
            payload=payload,
        )
    )
    db.commit()
    db.refresh(run)
    return run


def list_run_events(db: Session, tenant_id: str, run_id: str) -> list[AgentEvent]:
    statement = (
        select(AgentEvent)
        .where(AgentEvent.tenant_id == tenant_id, AgentEvent.run_id == run_id)
        .order_by(AgentEvent.created_at)
    )
    return list(db.scalars(statement).all())


def grant_tokens(db: Session, data: TokenGrantCreate) -> TokenGrant:
    grant = TokenGrant(
        tenant_id=data.tenant_id,
        user_id=data.user_id,
        granted_tokens=data.granted_tokens,
        remaining_tokens=data.granted_tokens,
        reason=data.reason,
        granted_by_user_id=data.granted_by_user_id,
    )
    db.add(grant)
    db.commit()
    db.refresh(grant)
    return grant


def record_token_usage(db: Session, data: TokenUsageCreate) -> TokenUsageEvent:
    total = (
        data.prompt_tokens
        + data.completion_tokens
        + data.embedding_tokens
        + data.rerank_tokens
    )
    event = TokenUsageEvent(
        tenant_id=data.tenant_id,
        user_id=data.user_id,
        run_id=data.run_id,
        node_name=data.node_name,
        call_type=data.call_type,
        model_provider=data.model_provider,
        model_id=data.model_id,
        prompt_tokens=data.prompt_tokens,
        completion_tokens=data.completion_tokens,
        embedding_tokens=data.embedding_tokens,
        rerank_tokens=data.rerank_tokens,
        total_tokens=total,
        metadata_json=data.metadata_json,
    )
    db.add(event)
    quota = _find_user_quota(db, data.tenant_id, data.user_id)
    if quota is not None:
        quota.token_used += total
    db.commit()
    db.refresh(event)
    return event


def ensure_default_model_registry(db: Session) -> None:
    provider = db.scalars(
        select(ModelProvider).where(ModelProvider.name == "local_stub")
    ).first()
    if provider is None:
        provider = ModelProvider(name="local_stub", provider_type="stub", status="active")
        db.add(provider)
        db.flush()

    defaults = [
        {"role": "cheap_chat", "model_id": "stub-chat", "context_window": 8192},
        {"role": "builder", "model_id": "stub-builder", "context_window": 32768},
        {"role": "embedding", "model_id": "stub-embedding", "context_window": 8192},
    ]
    for item in defaults:
        existing = db.scalars(
            select(ModelRegistry).where(
                ModelRegistry.provider_id == provider.id,
                ModelRegistry.model_id == item["model_id"],
                ModelRegistry.role == item["role"],
            )
        ).first()
        if existing is not None:
            continue
        db.add(
            ModelRegistry(
                provider_id=provider.id,
                model_id=item["model_id"],
                role=item["role"],
                context_window=item["context_window"],
                input_cost_per_1k=0.0,
                output_cost_per_1k=0.0,
                supports_json_schema=item["role"] == "builder",
                supports_tools=item["role"] in {"cheap_chat", "builder"},
                status="active",
            )
        )
    db.commit()


def create_model_provider(db: Session, data: ModelProviderCreate) -> ModelProvider:
    provider = ModelProvider(
        name=data.name,
        provider_type=data.provider_type,
        base_url=data.base_url,
        status=data.status,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def list_model_providers(db: Session) -> list[ModelProvider]:
    return list(db.scalars(select(ModelProvider).order_by(ModelProvider.created_at)).all())


def create_model_registry_entry(db: Session, data: ModelRegistryCreate) -> ModelRegistry:
    provider = db.get(ModelProvider, data.provider_id)
    if provider is None:
        raise ValueError("provider not found")
    model = ModelRegistry(
        provider_id=data.provider_id,
        model_id=data.model_id,
        role=data.role,
        context_window=data.context_window,
        input_cost_per_1k=data.input_cost_per_1k,
        output_cost_per_1k=data.output_cost_per_1k,
        supports_json_schema=data.supports_json_schema,
        supports_tools=data.supports_tools,
        status=data.status,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def list_model_registry(db: Session, role: str | None = None) -> list[tuple[ModelRegistry, ModelProvider]]:
    statement = (
        select(ModelRegistry, ModelProvider)
        .join(ModelProvider, ModelProvider.id == ModelRegistry.provider_id)
        .where(ModelRegistry.status == "active", ModelProvider.status == "active")
        .order_by(ModelRegistry.created_at.desc(), ModelRegistry.id.desc())
    )
    if role:
        statement = statement.where(ModelRegistry.role == role)
    return list(db.execute(statement).all())


def select_model_for_role(db: Session, role: str) -> tuple[ModelRegistry, ModelProvider]:
    rows = list_model_registry(db, role)
    if not rows:
        ensure_default_model_registry(db)
        rows = list_model_registry(db, role)
    if not rows:
        raise ValueError(f"model role not configured: {role}")
    model, provider = rows[0]
    return model, provider


def read_quota(db: Session, tenant_id: str, user_id: str | None) -> dict[str, Any]:
    statement = select(TokenQuota).where(TokenQuota.tenant_id == tenant_id)
    if user_id:
        statement = statement.where(TokenQuota.user_id == user_id)
    else:
        statement = statement.where(TokenQuota.user_id.is_(None))
    quota = db.scalars(statement).first()
    if quota is None:
        return {"tenant_id": tenant_id, "user_id": user_id, "token_limit": 0, "token_used": 0, "token_remaining": 0}
    grant_total = _remaining_grants(db, tenant_id, user_id)
    remaining = max(0, quota.token_limit - quota.token_used) + grant_total
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "token_limit": quota.token_limit,
        "token_used": quota.token_used,
        "token_remaining": remaining,
    }


def create_project_snapshot(
    db: Session,
    tenant_id: str,
    owner_user_id: str,
    name: str,
    domain: str,
    blueprint: dict[str, Any],
) -> GeneratedProject:
    project = GeneratedProject(
        tenant_id=tenant_id,
        owner_user_id=owner_user_id,
        name=name,
        domain=domain,
        blueprint=blueprint,
    )
    db.add(project)
    db.flush()
    version = ProjectVersion(
        tenant_id=tenant_id,
        project_id=project.id,
        version_number=1,
        blueprint=blueprint,
        manifest={"files": []},
        diff_summary="initial blueprint",
        status="created",
    )
    db.add(version)
    db.flush()
    project.active_version_id = version.id
    db.commit()
    db.refresh(project)
    return project


def create_project_from_schema(db: Session, data: ProjectSnapshotCreate) -> GeneratedProject:
    return create_project_snapshot(
        db=db,
        tenant_id=data.tenant_id,
        owner_user_id=data.owner_user_id,
        name=data.name,
        domain=data.domain,
        blueprint=data.blueprint,
    )


def list_project_versions(db: Session, tenant_id: str, project_id: str) -> list[ProjectVersion]:
    statement = (
        select(ProjectVersion)
        .where(ProjectVersion.tenant_id == tenant_id, ProjectVersion.project_id == project_id)
        .order_by(ProjectVersion.version_number)
    )
    return list(db.scalars(statement).all())


def list_project_validations(
    db: Session,
    tenant_id: str,
    project_id: str,
    version_id: str | None = None,
) -> list[ProjectValidation]:
    statement = select(ProjectValidation).where(
        ProjectValidation.tenant_id == tenant_id,
        ProjectValidation.project_id == project_id,
    )
    if version_id:
        statement = statement.where(ProjectValidation.version_id == version_id)
    statement = statement.order_by(ProjectValidation.created_at)
    return list(db.scalars(statement).all())


def list_project_eval_reports(
    db: Session,
    tenant_id: str,
    project_id: str,
    version_id: str | None = None,
) -> list[ProjectEvalReport]:
    statement = select(ProjectEvalReport).where(
        ProjectEvalReport.tenant_id == tenant_id,
        ProjectEvalReport.project_id == project_id,
    )
    if version_id:
        statement = statement.where(ProjectEvalReport.version_id == version_id)
    statement = statement.order_by(ProjectEvalReport.created_at)
    return list(db.scalars(statement).all())


def rollback_project(db: Session, tenant_id: str, project_id: str, version_id: str) -> GeneratedProject:
    project = db.get(GeneratedProject, project_id)
    version = db.get(ProjectVersion, version_id)
    if project is None or version is None:
        raise ValueError("project or version not found")
    if project.tenant_id != tenant_id or version.tenant_id != tenant_id:
        raise ValueError("project or version not found")
    if version.project_id != project_id:
        raise ValueError("version does not belong to project")
    project.active_version_id = version.id
    project.blueprint = version.blueprint
    project.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(project)
    return project


def repair_project(
    db: Session,
    tenant_id: str,
    project_id: str,
    force: bool = False,
) -> dict[str, Any]:
    project = db.get(GeneratedProject, project_id)
    if project is None or project.tenant_id != tenant_id:
        raise ValueError("project not found")
    active_version = db.get(ProjectVersion, project.active_version_id) if project.active_version_id else None
    if active_version is None or active_version.tenant_id != tenant_id:
        raise ValueError("active version not found")

    current_validation = validate_generated_project(project.storage_path, active_version.manifest)
    if current_validation["status"] == "passed" and not force:
        return {
            "project_id": project.id,
            "repaired": False,
            "reason": "active version already passes validation",
            "active_version_id": active_version.id,
            "validation": current_validation["summary"] | {"status": current_validation["status"]},
        }

    next_number = int(
        db.scalar(
            select(func.coalesce(func.max(ProjectVersion.version_number), 0)).where(
                ProjectVersion.tenant_id == tenant_id,
                ProjectVersion.project_id == project.id,
            )
        )
        or 0
    ) + 1
    version = ProjectVersion(
        tenant_id=tenant_id,
        project_id=project.id,
        version_number=next_number,
        blueprint=project.blueprint,
        manifest={"files": []},
        diff_summary="repair generated project from active blueprint",
        status="repaired",
        created_by_run_id=active_version.created_by_run_id,
    )
    db.add(version)
    db.flush()

    artifact = write_generated_project(project.id, project.blueprint)
    project.storage_path = artifact["storage_path"]
    version.manifest = {
        "files": artifact["files"],
        "file_count": artifact["file_count"],
        "storage_path": artifact["storage_path"],
    }
    validation_result = validate_generated_project(project.storage_path, version.manifest)
    db.add(
        ProjectValidation(
            tenant_id=tenant_id,
            project_id=project.id,
            version_id=version.id,
            status=validation_result["status"],
            checks=validation_result["checks"],
            summary=validation_result["summary"],
        )
    )
    eval_result = evaluate_generated_project(project.blueprint, validation_result)
    db.add(
        ProjectEvalReport(
            tenant_id=tenant_id,
            project_id=project.id,
            version_id=version.id,
            status=eval_result["status"],
            score=eval_result["score"],
            checks=eval_result["checks"],
            summary=eval_result["summary"],
        )
    )
    project.active_version_id = version.id
    project.status = "repaired" if validation_result["status"] == "passed" else "repair_failed"
    project.updated_at = datetime.now(timezone.utc)
    db.add(
        AgentEvent(
            tenant_id=tenant_id,
            run_id=active_version.created_by_run_id or project.id,
            node_name="project_repair",
            event_type="project.repair.completed",
            payload={
                "project_id": project.id,
                "previous_version_id": active_version.id,
                "new_version_id": version.id,
                "validation_status": validation_result["status"],
                "eval_status": eval_result["status"],
            },
            ok=validation_result["status"] == "passed" and eval_result["status"] == "passed",
        )
    )
    db.commit()
    db.refresh(project)
    db.refresh(version)
    return {
        "project_id": project.id,
        "repaired": True,
        "previous_version_id": active_version.id,
        "active_version_id": version.id,
        "version_number": version.version_number,
        "status": project.status,
        "validation": validation_result["summary"] | {"status": validation_result["status"]},
        "eval_report": {
            "status": eval_result["status"],
            "score": eval_result["score"],
            **eval_result["summary"],
        },
    }


def create_domain_template(db: Session, data: DomainTemplateCreate) -> DomainTemplate:
    status = _initial_domain_template_status(data)
    if status == "active":
        _deprecate_active_domain_templates(db, data.tenant_id, data.domain, data.name)
    template = DomainTemplate(
        tenant_id=data.tenant_id,
        domain=data.domain,
        name=data.name,
        version=data.version,
        compliance_profile=data.compliance_profile,
        required_modules=data.required_modules,
        default_prompts=data.default_prompts,
        required_eval_cases=data.required_eval_cases,
        status=status,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def list_pending_domain_templates(db: Session, tenant_id: str) -> list[DomainTemplate]:
    statement = (
        select(DomainTemplate)
        .where(DomainTemplate.tenant_id == tenant_id, DomainTemplate.status == "pending_review")
        .order_by(DomainTemplate.created_at)
    )
    return list(db.scalars(statement).all())


def decide_domain_template_review(
    db: Session,
    template_id: str,
    data: DomainTemplateReviewDecision,
) -> DomainTemplate:
    template = db.get(DomainTemplate, template_id)
    if template is None or template.tenant_id != data.tenant_id:
        raise ValueError("template not found")
    if template.status != "pending_review":
        raise ValueError("template is not pending review")

    if data.decision == "approve":
        _deprecate_active_domain_templates(db, template.tenant_id, template.domain, template.name)
        template.status = "active"
    elif data.decision == "reject":
        template.status = "rejected"
    else:
        raise ValueError("decision must be approve or reject")
    db.commit()
    db.refresh(template)
    return template


def update_domain_template_status(
    db: Session,
    template_id: str,
    data: DomainTemplateStatusUpdate,
) -> DomainTemplate:
    template = db.get(DomainTemplate, template_id)
    if template is None:
        raise ValueError("template not found")
    if template.tenant_id != data.tenant_id:
        raise ValueError("template not found")
    template.status = data.status
    db.commit()
    db.refresh(template)
    return template


def _initial_domain_template_status(data: DomainTemplateCreate) -> str:
    if data.tenant_id is None:
        return "active"
    risk_level = str(data.compliance_profile.get("risk_level", "")).lower()
    if risk_level == "high" or data.domain in {"law_firm", "hospital"}:
        return "pending_review"
    return "active"


def _deprecate_active_domain_templates(
    db: Session,
    tenant_id: str | None,
    domain: str,
    name: str,
) -> None:
    existing_active = db.scalars(
        select(DomainTemplate).where(
            DomainTemplate.tenant_id == tenant_id,
            DomainTemplate.domain == domain,
            DomainTemplate.name == name,
            DomainTemplate.status == "active",
        )
    ).all()
    for template in existing_active:
        template.status = "deprecated"


def ensure_default_domain_templates(db: Session) -> None:
    for item in DEFAULT_DOMAIN_TEMPLATES:
        existing = db.scalars(
            select(DomainTemplate).where(
                DomainTemplate.tenant_id.is_(None),
                DomainTemplate.domain == item["domain"],
                DomainTemplate.name == item["name"],
                DomainTemplate.version == item["version"],
            )
        ).first()
        if existing is not None:
            continue
        db.add(
            DomainTemplate(
                tenant_id=None,
                domain=item["domain"],
                name=item["name"],
                version=item["version"],
                compliance_profile=item["compliance_profile"],
                required_modules=item["required_modules"],
                default_prompts=item["default_prompts"],
                required_eval_cases=item["required_eval_cases"],
            )
        )
    db.commit()


def list_domain_templates(db: Session, tenant_id: str | None = None) -> list[DomainTemplate]:
    statement = select(DomainTemplate).where(DomainTemplate.status == "active")
    if tenant_id:
        statement = statement.where(
            (DomainTemplate.tenant_id == tenant_id) | (DomainTemplate.tenant_id.is_(None))
        )
    return list(db.scalars(statement).all())


def get_domain_template(
    db: Session,
    template_id: str,
    tenant_id: str | None = None,
) -> DomainTemplate:
    template = db.get(DomainTemplate, template_id)
    if template is None or template.status != "active":
        raise ValueError("template not found")
    if template.tenant_id is not None and template.tenant_id != tenant_id:
        raise ValueError("template not found")
    return template


def find_domain_template(
    db: Session,
    domain: str,
    tenant_id: str | None = None,
) -> DomainTemplate | None:
    templates = list_domain_templates(db, tenant_id)
    matches = [template for template in templates if template.domain == domain]
    if not matches:
        return None
    tenant_matches = [template for template in matches if template.tenant_id == tenant_id]
    if tenant_matches:
        return tenant_matches[-1]
    global_matches = [template for template in matches if template.tenant_id is None]
    return global_matches[-1] if global_matches else matches[-1]


def suggest_domain_template_improvements(
    db: Session,
    template_id: str,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    template = get_domain_template(db, template_id, tenant_id)
    feedback_rows = list(
        db.scalars(
            select(FeedbackItem)
            .where(FeedbackItem.tenant_id == (tenant_id or template.tenant_id))
            .order_by(FeedbackItem.created_at.desc())
            .limit(20)
        ).all()
    ) if tenant_id or template.tenant_id else []
    eval_rows = list(
        db.scalars(
            select(ProjectEvalReport)
            .where(ProjectEvalReport.status != "passed")
            .order_by(ProjectEvalReport.created_at.desc())
            .limit(20)
        ).all()
    )
    suggestions = []
    if any(row.rating < 0 for row in feedback_rows):
        suggestions.append(
            {
                "type": "feedback",
                "priority": "medium",
                "suggestion": "Review negative feedback and add missing eval cases or stricter prompts.",
            }
        )
    failed_checks = []
    for report in eval_rows:
        for check in report.checks:
            if not check.get("passed", True):
                failed_checks.append(check.get("name", "unknown"))
    if failed_checks:
        suggestions.append(
            {
                "type": "eval",
                "priority": "high",
                "suggestion": "Add template coverage for failing eval checks.",
                "failed_checks": sorted(set(failed_checks)),
            }
        )
    if "human_review" not in template.required_modules:
        suggestions.append(
            {
                "type": "module",
                "priority": "high",
                "suggestion": "Add human_review to required_modules for high-risk domains.",
            }
        )
    if "rag_with_citations" not in template.required_modules:
        suggestions.append(
            {
                "type": "module",
                "priority": "medium",
                "suggestion": "Add rag_with_citations to required_modules to enforce grounded answers.",
            }
        )
    return {
        "template_id": template.id,
        "domain": template.domain,
        "version": template.version,
        "feedback_count": len(feedback_rows),
        "failed_eval_report_count": len(eval_rows),
        "suggestions": suggestions,
    }


def create_feedback(db: Session, data: FeedbackCreate) -> FeedbackItem:
    item = FeedbackItem(
        tenant_id=data.tenant_id,
        user_id=data.user_id,
        run_id=data.run_id,
        rating=data.rating,
        category=data.category,
        comment=data.comment,
        correction=data.correction,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def pending_reviews(db: Session, tenant_id: str) -> list[HumanReviewRequest]:
    statement = select(HumanReviewRequest).where(
        HumanReviewRequest.tenant_id == tenant_id,
        HumanReviewRequest.status == "pending",
    )
    return list(db.scalars(statement).all())


def create_review_request(
    db: Session,
    run: AgentRun,
    state: dict[str, Any],
    reason: str,
) -> HumanReviewRequest:
    existing = db.scalars(
        select(HumanReviewRequest).where(
            HumanReviewRequest.tenant_id == run.tenant_id,
            HumanReviewRequest.run_id == run.id,
            HumanReviewRequest.status == "pending",
        )
    ).first()
    if existing is not None:
        return existing

    request = HumanReviewRequest(
        tenant_id=run.tenant_id,
        run_id=run.id,
        requester_user_id=run.user_id,
        risk_level=state.get("risk_level", "high"),
        reason=reason,
        proposed_action={
            "route": state.get("route"),
            "intent": state.get("intent"),
            "final_answer": state.get("final_answer", ""),
            "agent_blueprint": state.get("agent_blueprint"),
            "tool_plan": state.get("tool_plan", []),
        },
        evidence=state.get("rag_results", []),
    )
    db.add(request)
    db.flush()
    db.add(
        AgentEvent(
            tenant_id=run.tenant_id,
            run_id=run.id,
            node_name="human_review",
            event_type="review.pending",
            payload={"review_request_id": request.id, "reason": reason},
        )
    )
    return request


def decide_review(
    db: Session,
    review_id: str,
    data: ReviewDecisionCreate,
) -> tuple[HumanReviewRequest, HumanReviewDecision, AgentRun]:
    request = db.get(HumanReviewRequest, review_id)
    if request is None or request.tenant_id != data.tenant_id:
        raise ValueError("review not found")
    if request.status != "pending":
        raise ValueError("review already decided")
    if data.decision not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")

    run = db.get(AgentRun, request.run_id)
    if run is None or run.tenant_id != data.tenant_id:
        raise ValueError("run not found")

    decision = HumanReviewDecision(
        tenant_id=data.tenant_id,
        review_request_id=request.id,
        reviewer_user_id=data.reviewer_user_id,
        decision=data.decision,
        comment=data.comment,
        revised_action=data.revised_action,
    )
    request.status = "approved" if data.decision == "approve" else "rejected"
    request.decided_at = datetime.now(timezone.utc)
    run.status = "completed" if data.decision == "approve" else "rejected"
    output = dict(run.output_json or {})
    output["review_decision"] = {
        "decision": data.decision,
        "comment": data.comment,
        "revised_action": data.revised_action,
    }
    if data.decision == "reject":
        output["final_answer"] = "人工审核已拒绝该高风险动作。"
    elif data.revised_action:
        output["approved_action"] = data.revised_action
    if data.decision == "approve" and output.get("agent_blueprint"):
        project = GeneratedProject(
            tenant_id=run.tenant_id,
            owner_user_id=run.user_id,
            name=output["agent_blueprint"].get("name", "generated_agent"),
            domain=output["agent_blueprint"].get("domain", "generic"),
            blueprint=output["agent_blueprint"],
            status="blueprint_approved",
        )
        db.add(project)
        db.flush()
        version = ProjectVersion(
            tenant_id=run.tenant_id,
            project_id=project.id,
            version_number=1,
            blueprint=output["agent_blueprint"],
            manifest=output["agent_blueprint"].get("generated_project", {"files": []}),
            diff_summary="approved builder blueprint",
            status="approved",
            created_by_run_id=run.id,
        )
        db.add(version)
        db.flush()
        artifact = write_generated_project(project.id, output["agent_blueprint"])
        project.storage_path = artifact["storage_path"]
        version.manifest = {
            "files": artifact["files"],
            "file_count": artifact["file_count"],
            "storage_path": artifact["storage_path"],
        }
        validation_result = validate_generated_project(project.storage_path, version.manifest)
        validation = ProjectValidation(
            tenant_id=run.tenant_id,
            project_id=project.id,
            version_id=version.id,
            status=validation_result["status"],
            checks=validation_result["checks"],
            summary=validation_result["summary"],
        )
        db.add(validation)
        eval_result = evaluate_generated_project(output["agent_blueprint"], validation_result)
        eval_report = ProjectEvalReport(
            tenant_id=run.tenant_id,
            project_id=project.id,
            version_id=version.id,
            status=eval_result["status"],
            score=eval_result["score"],
            checks=eval_result["checks"],
            summary=eval_result["summary"],
        )
        db.add(eval_report)
        project.active_version_id = version.id
        output["generated_project"] = {
            "id": project.id,
            "active_version_id": version.id,
            "status": project.status,
            "storage_path": project.storage_path,
            "file_count": artifact["file_count"],
            "validation": validation_result["summary"] | {"status": validation_result["status"]},
            "eval_report": {
                "status": eval_result["status"],
                "score": eval_result["score"],
                **eval_result["summary"],
            },
        }
    run.output_json = output
    run.finished_at = datetime.now(timezone.utc)
    if data.decision == "approve":
        user_input = (
            run.input_json.get("message")
            or run.input_json.get("requirements")
            or str(run.input_json)
        )
        save_turn(
            db=db,
            tenant_id=run.tenant_id,
            user_id=run.user_id,
            session_id=run.session_id,
            user_input=user_input,
            assistant_output=output.get("final_answer", ""),
        )

    thread = db.scalars(
        select(GraphThread).where(
            GraphThread.tenant_id == run.tenant_id,
            GraphThread.thread_key == run.id,
        )
    ).first()
    if thread is not None:
        thread.status = run.status
        db.add(
            GraphCheckpoint(
                tenant_id=run.tenant_id,
                thread_id=thread.id,
                checkpoint_id=f"{run.id}:review:{data.decision}",
                state=output,
                metadata_json={
                    "run_id": run.id,
                    "review_request_id": request.id,
                    "decision": data.decision,
                },
            )
        )

    db.add(decision)
    db.add(
        AgentEvent(
            tenant_id=run.tenant_id,
            run_id=run.id,
            node_name="human_review",
            event_type="review.decided",
            payload={
                "review_request_id": request.id,
                "decision": data.decision,
                "reviewer_user_id": data.reviewer_user_id,
            },
        )
    )
    db.add(
        AgentEvent(
            tenant_id=run.tenant_id,
            run_id=run.id,
            node_name="runtime",
            event_type=f"run.{run.status}.after_review",
            payload={"review_request_id": request.id, "decision": data.decision},
        )
    )
    if output.get("generated_project", {}).get("validation"):
        db.add(
            AgentEvent(
                tenant_id=run.tenant_id,
                run_id=run.id,
                node_name="project_validator",
                event_type="project.validation.completed",
                payload=output["generated_project"]["validation"],
                ok=output["generated_project"]["validation"].get("status") == "passed",
            )
        )
    if output.get("generated_project", {}).get("eval_report"):
        db.add(
            AgentEvent(
                tenant_id=run.tenant_id,
                run_id=run.id,
                node_name="project_evaluator",
                event_type="project.eval.completed",
                payload=output["generated_project"]["eval_report"],
                ok=output["generated_project"]["eval_report"].get("status") == "passed",
            )
        )
    db.commit()
    db.refresh(request)
    db.refresh(decision)
    db.refresh(run)
    return request, decision, run


def _find_user_quota(db: Session, tenant_id: str, user_id: str) -> TokenQuota | None:
    statement = select(TokenQuota).where(
        TokenQuota.tenant_id == tenant_id,
        TokenQuota.user_id == user_id,
    )
    return db.scalars(statement).first()


def _remaining_grants(db: Session, tenant_id: str, user_id: str | None) -> int:
    statement = select(func.coalesce(func.sum(TokenGrant.remaining_tokens), 0)).where(
        TokenGrant.tenant_id == tenant_id,
        TokenGrant.user_id == user_id,
    )
    return int(db.scalar(statement) or 0)
