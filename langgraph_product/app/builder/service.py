"""多 Agent Builder。

这个模块把“用户想生成什么 Agent”转换成结构化 blueprint。
当前 specialist agent 是确定性函数，方便学习和测试；以后可以替换成真实 LLM，
但 blueprint 合同不变。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain_templates import DEFAULT_DOMAIN_TEMPLATES


@dataclass(frozen=True)
class BuilderInput:
    tenant_id: str
    user_id: str
    run_id: str
    product_name: str
    domain: str
    requirements: str
    domain_template: dict[str, Any] | None = None


def build_agent_blueprint(data: BuilderInput) -> dict[str, Any]:
    domain_template = _template_for(data)
    domain_profile = _domain_profile(data)
    specialists = [
        _requirements_agent(data),
        _architecture_agent(data),
        _data_agent(data),
        _rag_agent(data),
        _memory_agent(data),
        _tooling_agent(data),
        _human_review_agent(data),
        _security_agent(data),
        _test_agent(data),
        _code_manifest_agent(data),
    ]
    blueprint = {
        "schema_version": "1.0",
        "name": _safe_name(data.product_name, data.domain),
        "domain": data.domain,
        "requirements": data.requirements,
        "agents": specialists,
        "users": ["owner", "admin", "reviewer", "user"],
        "runtime": {
            "framework": "LangGraph",
            "api": "FastAPI",
            "worker": "RQ",
            "deployment": "Docker Compose first, Kubernetes later",
        },
        "graph": _graph_contract(data.domain),
        "database": _database_contract(),
        "rag": _rag_contract(data.domain),
        "memory": _memory_contract(),
        "human_review": _human_review_contract(data.domain),
        "tools": _tool_contracts(data.domain, domain_profile),
        "security": _security_contract(data.domain, domain_template),
        "observability": _observability_contract(),
        "domain_profile": domain_profile,
        "domain_template": _template_summary(domain_template),
        "generated_project": _project_manifest(data),
        "validation": _validate_blueprint_sections(specialists),
    }
    blueprint["readiness"] = {
        "status": "ready_for_project_generation"
        if blueprint["validation"]["ok"]
        else "needs_revision",
        "missing_modules": blueprint["validation"]["missing_modules"],
    }
    return blueprint


def _requirements_agent(data: BuilderInput) -> dict[str, Any]:
    domain_template = _template_for(data)
    domain_profile = _domain_profile(data)
    return {
        "name": "Requirements Agent",
        "role": "extract product scope and acceptance criteria",
        "output": {
            "primary_users": domain_profile["primary_users"],
            "core_use_cases": domain_profile["core_workflows"],
            "non_functional": ["tenant_isolation", "traceability", "token_budget"],
            "required_modules": domain_template.get("required_modules", []),
            "domain_entities": domain_profile["domain_entities"],
            "domain_tools": domain_profile["domain_tools"],
        },
    }


def _architecture_agent(data: BuilderInput) -> dict[str, Any]:
    return {
        "name": "Architecture Agent",
        "role": "define runtime architecture",
        "output": {
            "style": "modular monolith with worker boundary",
            "entrypoints": ["REST API", "SSE event stream", "worker jobs"],
            "graph_nodes": [
                "input_guard",
                "load_memory",
                "intent_router",
                "retrieve_knowledge",
                "plan_tools",
                "human_review",
                "execute_tools",
                "answer",
                "persist_run",
            ],
        },
    }


def _data_agent(data: BuilderInput) -> dict[str, Any]:
    domain_profile = _domain_profile(data)
    return {
        "name": "Data Architect Agent",
        "role": "define persistent schema",
        "output": {
            "database": "PostgreSQL",
            "vector": "pgvector",
            "tables": [
                "tenants",
                "users",
                "chat_sessions",
                "chat_messages",
                "user_memories",
                "knowledge_bases",
                "documents",
                "document_chunks",
                "agent_runs",
                "agent_events",
                "human_review_requests",
                "human_review_decisions",
                "token_usage_events",
            ]
            + [entity["table_name"] for entity in domain_profile["domain_entities"]],
        },
    }


def _rag_agent(data: BuilderInput) -> dict[str, Any]:
    return {
        "name": "RAG Engineer Agent",
        "role": "design retrieval and grounded answer flow",
        "output": _rag_contract(data.domain),
    }


def _memory_agent(data: BuilderInput) -> dict[str, Any]:
    return {
        "name": "Memory Engineer Agent",
        "role": "design memory lifecycle",
        "output": _memory_contract(),
    }


def _tooling_agent(data: BuilderInput) -> dict[str, Any]:
    domain_profile = _domain_profile(data)
    return {
        "name": "Tooling Agent",
        "role": "define safe tool contracts",
        "output": {"tools": _tool_contracts(data.domain, domain_profile), "sandbox_required": True},
    }


def _human_review_agent(data: BuilderInput) -> dict[str, Any]:
    return {
        "name": "Human Review Agent",
        "role": "define review gates and decisions",
        "output": _human_review_contract(data.domain),
    }


def _security_agent(data: BuilderInput) -> dict[str, Any]:
    return {
        "name": "Security Agent",
        "role": "define safety, privacy, and auth controls",
        "output": _security_contract(data.domain, _template_for(data)),
    }


def _test_agent(data: BuilderInput) -> dict[str, Any]:
    domain_template = _template_for(data)
    domain_profile = _domain_profile(data)
    return {
        "name": "Test Engineer Agent",
        "role": "define production validation plan",
        "output": {
            "unit": ["routing", "memory", "rag", "quota"],
            "integration": ["review approve/reject", "rag citation", "project version"],
            "evals": ["groundedness", "no-answer", "review-trigger", "domain-safety"],
            "domain_eval_cases": domain_template.get("required_eval_cases", []),
            "generated_domain_api_cases": [
                f"create_{entity['name']}" for entity in domain_profile["domain_entities"]
            ],
        },
    }


def _code_manifest_agent(data: BuilderInput) -> dict[str, Any]:
    return {
        "name": "Code Generator Agent",
        "role": "define generated repository shape",
        "output": _project_manifest(data),
    }


def _graph_contract(domain: str) -> dict[str, Any]:
    return {
        "routes": ["direct", "rag", "tool", "builder", "clarify", "reject"],
        "checkpoint": True,
        "interrupts": ["human_review"],
        "domain_risk": "high" if domain in {"law_firm", "hospital"} else "medium",
    }


def _database_contract() -> dict[str, Any]:
    return {
        "engine": "postgresql",
        "vector_extension": "pgvector",
        "cache": "redis",
        "migrations": "alembic",
        "tenant_isolation": True,
    }


def _rag_contract(domain: str) -> dict[str, Any]:
    return {
        "retrieval": "hybrid",
        "chunking": "heading-aware parent/leaf chunks",
        "citations_required": True,
        "no_answer_policy": "refuse when evidence is missing",
        "domain_filters": [domain, "tenant"],
    }


def _memory_contract() -> dict[str, Any]:
    return {
        "short_term": "chat_messages recent window",
        "summary": "chat_sessions.summary",
        "long_term": "user_memories with embedding",
        "privacy": "sensitive data requires explicit allowlist",
    }


def _human_review_contract(domain: str) -> dict[str, Any]:
    return {
        "required_for": [
            "professional_advice",
            "external_send",
            "database_write",
            "file_delete",
            "generated_project_publish",
        ],
        "roles": ["reviewer", "admin", "owner"],
        "decisions": ["approve", "reject", "revise", "needs_more_info"],
        "default_required": domain in {"law_firm", "hospital"},
    }


def _tool_contracts(
    domain: str,
    domain_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    tools = [
        {"name": "knowledge_search", "risk": "low", "review_required": False},
        {"name": "document_export", "risk": "medium", "review_required": True},
        {"name": "project_file_writer", "risk": "high", "review_required": True},
    ]
    if domain == "law_firm":
        tools.append({"name": "case_lookup", "risk": "high", "review_required": True})
    if domain == "hospital":
        tools.append({"name": "patient_record_lookup", "risk": "high", "review_required": True})
    if domain_profile:
        existing = {tool["name"] for tool in tools}
        for tool in domain_profile.get("domain_tools", []):
            if tool["name"] not in existing:
                tools.append(tool)
    return tools


def _security_contract(domain: str, domain_template: dict[str, Any]) -> dict[str, Any]:
    sensitive = ["PII"]
    if domain == "hospital":
        sensitive.append("PHI")
    if domain == "law_firm":
        sensitive.append("attorney_client_privileged")
    return {
        "auth": "API token first, OAuth/SSO extension",
        "rbac": ["owner", "admin", "reviewer", "user"],
        "audit_log": True,
        "sensitive_data": sensitive,
        "prompt_injection_defense": True,
        "compliance_profile": domain_template.get("compliance_profile", {}),
    }


def _observability_contract() -> dict[str, Any]:
    return {
        "events": ["run.created", "node.completed", "review.pending", "review.decided"],
        "metrics": ["latency", "token_usage", "retrieval_hit_rate", "review_pending_count"],
        "traces": ["run_id", "node_name", "model_id"],
    }


def _project_manifest(data: BuilderInput) -> dict[str, Any]:
    return {
        "root": _safe_name(data.product_name, data.domain),
        "files": [
            "app/main.py",
            "app/graph.py",
            "app/models.py",
            "app/domain/models.py",
            "app/domain/routes.py",
            "app/tools/registry.py",
            "app/rag/service.py",
            "app/memory/service.py",
            "app/human_review/service.py",
            "tests/test_graph.py",
            "tests/test_rag.py",
            "tests/test_human_review.py",
            "docker-compose.yml",
            "README.md",
        ],
    }


def _domain_profile(data: BuilderInput) -> dict[str, Any]:
    text = f"{data.domain} {data.product_name} {data.requirements}".lower()
    industry = _humanize(data.domain or data.product_name)
    risk_level = "high" if data.domain in {"law_firm", "hospital"} else "medium"
    if any(word in text for word in ["medical", "hospital", "patient", "法律", "律所", "合规", "finance", "trading"]):
        risk_level = "high"

    presets = {
        "real_estate": {
            "entities": ["property", "lead", "viewing", "deal"],
            "workflows": ["match_properties", "qualify_leads", "schedule_viewings", "summarize_deals"],
            "users": ["agent", "manager", "client"],
        },
        "ecommerce": {
            "entities": ["product", "order", "refund", "support_ticket"],
            "workflows": ["answer_order_questions", "triage_refunds", "recommend_products", "escalate_tickets"],
            "users": ["support_agent", "customer", "operations_manager"],
        },
        "investment": {
            "entities": ["company", "research_report", "portfolio", "signal"],
            "workflows": ["summarize_research", "compare_companies", "track_signals", "draft_investment_memos"],
            "users": ["analyst", "portfolio_manager", "reviewer"],
        },
        "education": {
            "entities": ["student", "course", "assignment", "learning_plan"],
            "workflows": ["answer_course_questions", "grade_with_review", "recommend_learning_plan", "track_progress"],
            "users": ["teacher", "student", "academic_admin"],
        },
        "law_firm": {
            "entities": ["client", "matter", "contract", "legal_review"],
            "workflows": ["knowledge_qa", "draft_legal_documents", "conflict_check", "lawyer_review"],
            "users": ["lawyer", "paralegal", "reviewer"],
        },
        "hospital": {
            "entities": ["patient", "encounter", "clinical_note", "care_task"],
            "workflows": ["clinical_knowledge_qa", "summarize_notes", "route_care_tasks", "clinician_review"],
            "users": ["clinician", "nurse", "care_admin"],
        },
    }
    preset_key = _preset_key(text, data.domain)
    preset = presets.get(
        preset_key,
        {
            "entities": _fallback_entities(data.domain, data.requirements),
            "workflows": ["knowledge_qa", "document_intake", "draft_response", "human_review"],
            "users": ["business_user", "reviewer", "admin"],
        },
    )
    entities = [_entity_contract(name) for name in preset["entities"][:6]]
    workflows = preset["workflows"][:6]
    tools = [
        {
            "name": f"{entity['name']}_lookup",
            "risk": "medium" if risk_level == "medium" else "high",
            "review_required": risk_level == "high",
            "input_schema": {"query": "string", "tenant_id": "string"},
            "description": f"Lookup {entity['display_name']} records for the generated domain.",
        }
        for entity in entities
    ]
    return {
        "industry": industry,
        "risk_level": risk_level,
        "primary_users": preset["users"],
        "core_workflows": workflows,
        "domain_entities": entities,
        "domain_tools": tools,
        "rag_sources": ["uploaded_documents", "domain_knowledge_base"],
        "human_review_triggers": [
            "external_send",
            "high_risk_recommendation",
            "sensitive_data_access",
        ],
        "eval_cases": [
            {
                "name": f"{workflow}_smoke",
                "input": f"Run {workflow} for a sample {industry} request.",
                "expected": {"safe_response": True},
            }
            for workflow in workflows[:3]
        ],
    }


def _preset_key(text: str, domain: str) -> str:
    normalized = domain.lower()
    if normalized in {"real_estate", "ecommerce", "investment", "education", "law_firm", "hospital"}:
        return normalized
    if any(word in text for word in ["房产", "中介", "real estate", "property"]):
        return "real_estate"
    if any(word in text for word in ["电商", "订单", "退款", "ecommerce", "shop"]):
        return "ecommerce"
    if any(word in text for word in ["投研", "股票", "投资", "investment", "research"]):
        return "investment"
    if any(word in text for word in ["教育", "课程", "学生", "education", "course"]):
        return "education"
    return normalized


def _fallback_entities(domain: str, requirements: str) -> list[str]:
    text = f"{domain} {requirements}".lower()
    candidates = []
    for raw in text.replace("/", " ").replace(",", " ").replace("，", " ").split():
        token = "".join(char for char in raw if char.isalnum() or char == "_").strip("_")
        if 3 <= len(token) <= 24 and token not in {"agent", "project", "生成", "需要"}:
            candidates.append(token)
    base = [domain.strip() or "domain", "task", "record", "workflow"]
    names = []
    for item in candidates + base:
        safe = _safe_identifier(item)
        if safe and safe not in names:
            names.append(safe)
        if len(names) >= 4:
            break
    return names or ["domain_record", "task", "workflow"]


def _entity_contract(name: str) -> dict[str, Any]:
    safe = _safe_identifier(name)
    return {
        "name": safe,
        "class_name": _class_name(safe),
        "table_name": f"domain_{_pluralize(safe)}",
        "display_name": safe.replace("_", " "),
        "fields": [
            {"name": "title", "type": "str", "required": True},
            {"name": "status", "type": "str", "required": False},
            {"name": "summary", "type": "str", "required": False},
            {"name": "metadata_json", "type": "dict", "required": False},
        ],
    }


def _safe_identifier(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "_" for char in value)
    parts = [part for part in normalized.split("_") if part]
    identifier = "_".join(parts)
    if not identifier:
        return "domain_record"
    if identifier[0].isdigit():
        identifier = f"entity_{identifier}"
    return identifier[:40]


def _class_name(value: str) -> str:
    return "".join(part.capitalize() for part in value.split("_") if part) or "DomainRecord"


def _pluralize(value: str) -> str:
    if value.endswith("y"):
        return value[:-1] + "ies"
    if value.endswith("s"):
        return value + "es"
    return value + "s"


def _humanize(value: str) -> str:
    return _safe_identifier(value).replace("_", " ").title()


def _validate_blueprint_sections(specialists: list[dict[str, Any]]) -> dict[str, Any]:
    required = {
        "Requirements Agent",
        "Architecture Agent",
        "Data Architect Agent",
        "RAG Engineer Agent",
        "Memory Engineer Agent",
        "Human Review Agent",
        "Security Agent",
        "Test Engineer Agent",
        "Code Generator Agent",
    }
    names = {item["name"] for item in specialists}
    missing = sorted(required - names)
    return {"ok": not missing, "missing_modules": missing, "specialist_count": len(specialists)}


def _default_template(domain: str) -> dict[str, Any]:
    for template in DEFAULT_DOMAIN_TEMPLATES:
        if template["domain"] == domain:
            return template
    return {
        "domain": domain,
        "name": "Generic Agent Template",
        "version": "1.0.0",
        "compliance_profile": {"risk_level": "medium"},
        "required_modules": [],
        "default_prompts": {},
        "required_eval_cases": [],
    }


def _template_for(data: BuilderInput) -> dict[str, Any]:
    return data.domain_template or _default_template(data.domain)


def _template_summary(template: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain": template["domain"],
        "name": template["name"],
        "version": template["version"],
        "required_modules": template.get("required_modules", []),
        "default_prompts": template.get("default_prompts", {}),
        "required_eval_cases": template.get("required_eval_cases", []),
        "compliance_profile": template.get("compliance_profile", {}),
    }


def _safe_name(product_name: str, domain: str) -> str:
    raw = product_name.strip() or f"{domain}_agent"
    allowed = [char.lower() if char.isalnum() else "_" for char in raw]
    compact = "".join(allowed).strip("_")
    return compact or f"{domain}_agent"
