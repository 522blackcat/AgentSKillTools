"""Production-readiness evals for generated agent projects."""

from __future__ import annotations

from typing import Any


def evaluate_generated_project(
    blueprint: dict[str, Any],
    validation_result: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        _eval_rag(blueprint),
        _eval_memory(blueprint),
        _eval_human_review(blueprint),
        _eval_security(blueprint),
        _eval_database(blueprint),
        _eval_testing(blueprint),
        _eval_observability(blueprint),
        _eval_domain_template(blueprint),
        _eval_runtime_validation(validation_result),
    ]
    passed = [item for item in checks if item["passed"]]
    score = round(len(passed) / len(checks), 3)
    return {
        "status": "passed" if score >= 1.0 else "failed",
        "score": score,
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": len(passed),
            "failed": len(checks) - len(passed),
        },
    }


def _eval_rag(blueprint: dict[str, Any]) -> dict[str, Any]:
    rag = blueprint.get("rag", {})
    passed = bool(
        rag.get("retrieval")
        and rag.get("citations_required") is True
        and rag.get("no_answer_policy")
    )
    return _result("rag_grounding", passed, rag)


def _eval_memory(blueprint: dict[str, Any]) -> dict[str, Any]:
    memory = blueprint.get("memory", {})
    passed = all(memory.get(key) for key in ("short_term", "summary", "long_term"))
    return _result("three_layer_memory", passed, memory)


def _eval_human_review(blueprint: dict[str, Any]) -> dict[str, Any]:
    review = blueprint.get("human_review", {})
    decisions = set(review.get("decisions", []))
    passed = {"approve", "reject"}.issubset(decisions) and bool(review.get("required_for"))
    return _result("human_review_gates", passed, review)


def _eval_security(blueprint: dict[str, Any]) -> dict[str, Any]:
    security = blueprint.get("security", {})
    passed = bool(security.get("rbac")) and security.get("audit_log") is True
    return _result("security_controls", passed, security)


def _eval_database(blueprint: dict[str, Any]) -> dict[str, Any]:
    database = blueprint.get("database", {})
    passed = (
        database.get("engine") == "postgresql"
        and database.get("vector_extension") == "pgvector"
        and database.get("tenant_isolation") is True
    )
    return _result("database_production_store", passed, database)


def _eval_testing(blueprint: dict[str, Any]) -> dict[str, Any]:
    agent = _agent_output(blueprint, "Test Engineer Agent")
    passed = bool(agent.get("unit")) and bool(agent.get("integration")) and bool(agent.get("evals"))
    return _result("test_strategy", passed, agent)


def _eval_observability(blueprint: dict[str, Any]) -> dict[str, Any]:
    observability = blueprint.get("observability", {})
    passed = bool(observability.get("events")) and bool(observability.get("metrics"))
    return _result("observability", passed, observability)


def _eval_runtime_validation(validation_result: dict[str, Any]) -> dict[str, Any]:
    detail = validation_result.get("summary", {}) | {"status": validation_result.get("status")}
    return _result("runtime_validation", validation_result.get("status") == "passed", detail)


def _eval_domain_template(blueprint: dict[str, Any]) -> dict[str, Any]:
    template = blueprint.get("domain_template", {})
    required_modules = set(template.get("required_modules", []))
    eval_cases = template.get("required_eval_cases", [])
    needed = {"rag_with_citations", "human_review", "audit_log", "token_accounting"}
    passed = needed.issubset(required_modules) and bool(eval_cases)
    return _result("domain_template_coverage", passed, template)


def _agent_output(blueprint: dict[str, Any], agent_name: str) -> dict[str, Any]:
    for agent in blueprint.get("agents", []):
        if agent.get("name") == agent_name:
            return agent.get("output", {})
    return {}


def _result(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "passed": passed, "detail": detail}
