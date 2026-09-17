"""Run 执行入口。

一次 run 会在这里加载 memory、RAG、领域模板、模型配置和 token budget，
然后进入 LangGraph。Graph 返回后，这里负责写事件、checkpoint、token usage，
并处理 completed / awaiting_review / failed 等状态。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from sqlalchemy import select

from app.config import settings
from app.builder.evals import evaluate_generated_project
from app.builder.project_writer import write_generated_project
from app.builder.validator import validate_generated_project
from app.database.models import AgentEvent, AgentRun, DomainTemplate, GraphCheckpoint, GraphThread, TokenQuota
from app.database.models import TokenUsageEvent
from app.database.models import GeneratedProject, ProjectEvalReport, ProjectValidation, ProjectVersion
from app.database.models import now_utc
from app.graph.builder import agent_graph
from app.knowledge.service import build_rag_context, search_knowledge_base
from app.memory.service import load_memory_context, save_turn
from app.model_gateway.gateway import _estimate_tokens
from app.schemas import KnowledgeSearchRequest
from app.services import create_review_request, list_model_registry, read_quota, select_model_for_role


def invoke_agent_run(db: Session, run_id: str) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if run is None:
        raise ValueError("run not found")
    run.status = "running"
    run.started_at = now_utc()
    db.commit()

    if run.graph_name == "agent_builder":
        user_input = (
            f"构建 {run.input_json.get('domain', 'generic')} "
            f"{run.input_json.get('product_name', 'agent')}。"
            f"{run.input_json.get('requirements', '')}"
        )
    else:
        user_input = (
            run.input_json.get("message")
            or run.input_json.get("requirements")
            or str(run.input_json)
        )
    estimated_input_tokens = _estimate_tokens(user_input)
    quota = read_quota(db, run.tenant_id, run.user_id)
    if quota["token_remaining"] < estimated_input_tokens:
        run.status = "quota_exceeded"
        run.output_json = {
            "final_answer": "当前用户 token 额度不足，无法执行本次请求。",
            "quota": quota,
            "estimated_input_tokens": estimated_input_tokens,
        }
        db.commit()
        db.refresh(run)
        return run
    chat_model, chat_provider = select_model_for_role(db, "cheap_chat")
    model_candidates = [
        {
            "model_provider": provider.name,
            "provider_type": provider.provider_type,
            "model_id": model.model_id,
            "base_url": provider.base_url,
            "api_key": settings.api_key,
            "input_cost_per_1k": float(model.input_cost_per_1k),
            "output_cost_per_1k": float(model.output_cost_per_1k),
        }
        for model, provider in list_model_registry(db, "cheap_chat")
    ]
    memory_context = load_memory_context(
        db=db,
        tenant_id=run.tenant_id,
        user_id=run.user_id,
        session_id=run.session_id,
        query=user_input,
    )
    knowledge_base_id = run.input_json.get("knowledge_base_id")
    rag_results: list[dict] = []
    rag_context = ""
    if knowledge_base_id:
        rag_response = search_knowledge_base(
            db,
            knowledge_base_id,
            KnowledgeSearchRequest(
                tenant_id=run.tenant_id,
                query=user_input,
                top_k=5,
                run_id=run.id,
            ),
        )
        rag_results = rag_response["results"]
        rag_context = build_rag_context(rag_results)
    builder_domain_template = None
    domain_template_id = run.input_json.get("domain_template_id")
    if domain_template_id:
        template = db.get(DomainTemplate, domain_template_id)
        if (
            template is None
            or template.status != "active"
            or template.tenant_id not in {None, run.tenant_id}
        ):
            raise ValueError("domain template not found")
        builder_domain_template = {
            "domain": template.domain,
            "name": template.name,
            "version": template.version,
            "compliance_profile": template.compliance_profile,
            "required_modules": template.required_modules,
            "default_prompts": template.default_prompts,
            "required_eval_cases": template.required_eval_cases,
        }
    state = {
        "tenant_id": run.tenant_id,
        "user_id": run.user_id,
        "session_id": run.session_id,
        "run_id": run.id,
        "user_input": user_input,
        "messages": memory_context.recent_messages,
        "memory_context": memory_context.to_prompt_context(),
        "memory_candidates": memory_context.long_term_memories,
        "knowledge_base_id": knowledge_base_id,
        "builder_domain": run.input_json.get("domain", ""),
        "builder_product_name": run.input_json.get("product_name", ""),
        "builder_domain_template": builder_domain_template,
        "model_provider": chat_provider.name,
        "model_provider_type": chat_provider.provider_type,
        "model_id": chat_model.model_id,
        "model_base_url": chat_provider.base_url,
        "model_api_key": settings.api_key,
        "model_input_cost_per_1k": float(chat_model.input_cost_per_1k),
        "model_output_cost_per_1k": float(chat_model.output_cost_per_1k),
        "model_fallbacks": model_candidates[1:],
        "rag_query": user_input if knowledge_base_id else "",
        "rag_results": rag_results,
        "rag_context": rag_context,
        "trace": [],
    }
    try:
        result = agent_graph.invoke(state)
    except Exception as exc:  # noqa: BLE001 - runtime must persist failed run state.
        run.status = "failed"
        run.output_json = {
            "final_answer": "模型调用失败，且没有可用 fallback。",
            "error": {"type": exc.__class__.__name__, "message": str(exc)},
        }
        db.add(
            AgentEvent(
                tenant_id=run.tenant_id,
                run_id=run.id,
                node_name="model_gateway",
                event_type="run.failed.model_gateway",
                payload=run.output_json["error"],
                ok=False,
                error=run.output_json["error"],
            )
        )
        run.finished_at = now_utc()
        db.commit()
        db.refresh(run)
        return run
    run.output_json = result

    if result.get("review_required"):
        run.status = "awaiting_review"
        thread = GraphThread(
            tenant_id=run.tenant_id,
            user_id=run.user_id,
            thread_key=run.id,
            graph_name=run.graph_name,
            status="awaiting_review",
        )
        db.add(thread)
        db.flush()
        db.add(
            GraphCheckpoint(
                tenant_id=run.tenant_id,
                thread_id=thread.id,
                checkpoint_id=f"{run.id}:awaiting_review",
                state=result,
                metadata_json={"run_id": run.id, "status": "awaiting_review"},
            )
        )
        for item in result.get("trace", []):
            db.add(
                AgentEvent(
                    tenant_id=run.tenant_id,
                    run_id=run.id,
                    node_name=item.get("node", "graph"),
                    event_type="node.completed",
                    payload=item,
                    ok=item.get("ok", True),
                )
            )
        if result.get("agent_blueprint"):
            db.add(
                AgentEvent(
                    tenant_id=run.tenant_id,
                    run_id=run.id,
                    node_name="agent_builder_supervisor",
                    event_type="builder.blueprint.created",
                    payload={
                        "name": result["agent_blueprint"].get("name"),
                        "domain": result["agent_blueprint"].get("domain"),
                        "ready": result["agent_blueprint"].get("readiness", {}).get("status"),
                    },
                )
            )
        review = create_review_request(
            db,
            run,
            result,
            reason="Graph marked this run as requiring human review.",
        )
        output = dict(result)
        output["review_request"] = {
            "id": review.id,
            "status": review.status,
            "risk_level": review.risk_level,
        }
        run.output_json = output
        db.commit()
        db.refresh(run)
        return run

    run.status = "completed"
    run.finished_at = now_utc()
    if run.graph_name == "agent_builder" and result.get("agent_blueprint"):
        project = GeneratedProject(
            tenant_id=run.tenant_id,
            owner_user_id=run.user_id,
            name=result["agent_blueprint"].get("name", "generated_agent"),
            domain=result["agent_blueprint"].get("domain", "generic"),
            blueprint=result["agent_blueprint"],
            status="blueprint_generated",
        )
        db.add(project)
        db.flush()
        version = ProjectVersion(
            tenant_id=run.tenant_id,
            project_id=project.id,
            version_number=1,
            blueprint=result["agent_blueprint"],
            manifest=result["agent_blueprint"].get("generated_project", {"files": []}),
            diff_summary="generated builder blueprint",
            status="generated",
            created_by_run_id=run.id,
        )
        db.add(version)
        db.flush()
        artifact = write_generated_project(project.id, result["agent_blueprint"])
        project.storage_path = artifact["storage_path"]
        version.manifest = {
            "files": artifact["files"],
            "file_count": artifact["file_count"],
            "storage_path": artifact["storage_path"],
        }
        validation_result = validate_generated_project(project.storage_path, version.manifest)
        db.add(
            ProjectValidation(
                tenant_id=run.tenant_id,
                project_id=project.id,
                version_id=version.id,
                status=validation_result["status"],
                checks=validation_result["checks"],
                summary=validation_result["summary"],
            )
        )
        eval_result = evaluate_generated_project(result["agent_blueprint"], validation_result)
        db.add(
            ProjectEvalReport(
                tenant_id=run.tenant_id,
                project_id=project.id,
                version_id=version.id,
                status=eval_result["status"],
                score=eval_result["score"],
                checks=eval_result["checks"],
                summary=eval_result["summary"],
            )
        )
        project.active_version_id = version.id
        result = dict(result)
        result["generated_project"] = {
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
        run.output_json = result
        db.add(
            AgentEvent(
                tenant_id=run.tenant_id,
                run_id=run.id,
                node_name="project_generator",
                event_type="project.generated",
                payload=result["generated_project"],
                ok=validation_result["status"] == "passed",
            )
        )
    save_turn(
        db=db,
        tenant_id=run.tenant_id,
        user_id=run.user_id,
        session_id=run.session_id,
        user_input=user_input,
        assistant_output=result.get("final_answer", ""),
    )
    thread = GraphThread(
        tenant_id=run.tenant_id,
        user_id=run.user_id,
        thread_key=run.id,
        graph_name=run.graph_name,
        status="completed",
    )
    db.add(thread)
    db.flush()
    db.add(
        GraphCheckpoint(
            tenant_id=run.tenant_id,
            thread_id=thread.id,
            checkpoint_id=f"{run.id}:completed",
            state=result,
            metadata_json={"run_id": run.id, "status": "completed"},
        )
    )
    for item in result.get("trace", []):
        db.add(
            AgentEvent(
                tenant_id=run.tenant_id,
                run_id=run.id,
                node_name=item.get("node", "graph"),
                event_type="node.completed",
                payload=item,
                ok=item.get("ok", True),
            )
        )
    usage = result.get("token_usage") or {}
    total_tokens = int(usage.get("total_tokens", 0) or 0)
    if total_tokens:
        db.add(
            TokenUsageEvent(
                tenant_id=run.tenant_id,
                user_id=run.user_id,
                run_id=run.id,
                node_name="graph",
                call_type="chat_completion",
                model_provider=usage.get("model_provider", chat_provider.name),
                model_id=usage.get("model_id", chat_model.model_id),
                prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                total_tokens=total_tokens,
                estimated_cost=float(usage.get("estimated_cost", 0.0) or 0.0),
                metadata_json={
                    "estimated": usage.get("estimated", True),
                    "provider_type": usage.get("provider_type", chat_provider.provider_type),
                    "failed_over": usage.get("failed_over", False),
                    "attempts": usage.get("attempts", []),
                },
            )
        )
        quota = db.scalars(
            select(TokenQuota).where(
                TokenQuota.tenant_id == run.tenant_id,
                TokenQuota.user_id == run.user_id,
            )
        ).first()
        if quota is not None:
            quota.token_used += total_tokens
    db.commit()
    db.refresh(run)
    return run
