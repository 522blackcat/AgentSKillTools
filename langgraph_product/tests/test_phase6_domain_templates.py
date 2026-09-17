from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import auth_headers


def test_default_domain_templates_are_seeded_and_queryable() -> None:
    with TestClient(app) as client:
        seeded = client.post("/v1/domain-templates/defaults/seed")
        assert seeded.status_code == 200, seeded.text

        templates = client.get("/v1/domain-templates")
        assert templates.status_code == 200, templates.text
        payload = templates.json()
        domains = {item["domain"] for item in payload}
        assert {"law_firm", "hospital"}.issubset(domains)

        law_template = next(item for item in payload if item["domain"] == "law_firm")
        detail = client.get(f"/v1/domain-templates/{law_template['id']}")
        assert detail.status_code == 200, detail.text
        body = detail.json()
        assert "human_review" in body["required_modules"]
        assert "rag_with_citations" in body["required_modules"]
        assert body["compliance_profile"]["risk_level"] == "high"
        assert body["required_eval_cases"]


def test_builder_blueprint_includes_domain_template_contract() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase6"}).json()
        owner = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "phase6-owner@example.com",
                "username": "phase6-owner",
                "role": "owner",
            },
        ).json()
        run = client.post(
            "/v1/builder/runs",
            json={
                "tenant_id": tenant["id"],
                "user_id": owner["id"],
                "domain": "hospital",
                "product_name": "Hospital Agent",
                "requirements": "需要病历问答、临床审核、PHI 隐私保护。",
            },
        ).json()
        invoked = client.post(
            f"/v1/builder/runs/{run['id']}/invoke",
            params={"tenant_id": tenant["id"]},
        )
        assert invoked.status_code == 200, invoked.text
        blueprint = invoked.json()["output_json"]["agent_blueprint"]
        template = blueprint["domain_template"]
        assert template["domain"] == "hospital"
        assert "phi_privacy_filter" in template["required_modules"]
        assert template["required_eval_cases"]
        assert blueprint["security"]["compliance_profile"]["sensitive_data"] == ["PII", "PHI"]

        approved = client.post(
            f"/v1/reviews/{invoked.json()['output_json']['review_request']['id']}/decide",
            headers=auth_headers(client, tenant["id"], owner["id"]),
            json={
                "tenant_id": tenant["id"],
                "reviewer_user_id": owner["id"],
                "decision": "approve",
            },
        )
        assert approved.status_code == 200, approved.text
        fetched = client.get(
            f"/v1/chat/runs/{run['id']}",
            params={"tenant_id": tenant["id"]},
        )
        generated_project = fetched.json()["output_json"]["generated_project"]
        eval_reports = client.get(
            f"/v1/generated-projects/{generated_project['id']}/eval-reports",
            params={"tenant_id": tenant["id"]},
        ).json()
        eval_names = {check["name"] for check in eval_reports[0]["checks"]}
        assert "domain_template_coverage" in eval_names


def test_builder_can_use_tenant_custom_domain_template() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase6 Custom"}).json()
        owner = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "custom-owner@example.com",
                "username": "custom-owner",
                "role": "owner",
            },
        ).json()
        custom_template = client.post(
            "/v1/domain-templates",
            json={
                "tenant_id": tenant["id"],
                "domain": "law_firm",
                "name": "Tenant Law Template",
                "version": "2.0.0",
                "compliance_profile": {
                    "risk_level": "high",
                    "sensitive_data": ["PII", "custom_matter_secret"],
                },
                "required_modules": [
                    "rag_with_citations",
                    "human_review",
                    "audit_log",
                    "token_accounting",
                    "custom_conflict_check",
                ],
                "default_prompts": {
                    "system": "Tenant-specific law firm system prompt.",
                    "no_answer": "Tenant no-answer policy.",
                },
                "required_eval_cases": [
                    {
                        "name": "tenant_conflict_check",
                        "input": "新客户咨询前检查利益冲突。",
                        "expected": {"custom_conflict_check": True},
                    }
                ],
            },
        )
        assert custom_template.status_code == 200, custom_template.text
        assert custom_template.json()["status"] == "pending_review"
        unapproved_run = client.post(
            "/v1/builder/runs",
            json={
                "tenant_id": tenant["id"],
                "user_id": owner["id"],
                "domain": "law_firm",
                "product_name": "Unapproved Law Agent",
                "requirements": "未审批模板不能被使用。",
                "domain_template_id": custom_template.json()["id"],
            },
        ).json()
        unapproved_invoked = client.post(
            f"/v1/builder/runs/{unapproved_run['id']}/invoke",
            params={"tenant_id": tenant["id"]},
        )
        assert unapproved_invoked.status_code == 404

        approved_template = client.post(
            f"/v1/domain-templates/{custom_template.json()['id']}/review",
            headers=auth_headers(client, tenant["id"], owner["id"]),
            json={
                "tenant_id": tenant["id"],
                "reviewer_user_id": owner["id"],
                "decision": "approve",
                "comment": "Approved tenant law template.",
            },
        )
        assert approved_template.status_code == 200, approved_template.text
        assert approved_template.json()["status"] == "active"

        run = client.post(
            "/v1/builder/runs",
            json={
                "tenant_id": tenant["id"],
                "user_id": owner["id"],
                "domain": "law_firm",
                "product_name": "Custom Law Agent",
                "requirements": "必须先做利益冲突检查。",
                "domain_template_id": custom_template.json()["id"],
            },
        ).json()
        invoked = client.post(
            f"/v1/builder/runs/{run['id']}/invoke",
            params={"tenant_id": tenant["id"]},
        )
        assert invoked.status_code == 200, invoked.text
        blueprint = invoked.json()["output_json"]["agent_blueprint"]
        template = blueprint["domain_template"]
        assert template["name"] == "Tenant Law Template"
        assert template["version"] == "2.0.0"
        assert "custom_conflict_check" in template["required_modules"]
        assert blueprint["security"]["compliance_profile"]["sensitive_data"] == [
            "PII",
            "custom_matter_secret",
        ]


def test_tenant_template_versions_and_feedback_suggestions() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase6 Feedback"}).json()
        user = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "feedback-owner@example.com",
                "username": "feedback-owner",
                "role": "owner",
            },
        ).json()
        first = client.post(
            "/v1/domain-templates",
            json={
                "tenant_id": tenant["id"],
                "domain": "law_firm",
                "name": "Versioned Law Template",
                "version": "1.0.0",
                "compliance_profile": {"risk_level": "high"},
                "required_modules": ["human_review"],
                "default_prompts": {"system": "v1"},
                "required_eval_cases": [],
            },
        )
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "pending_review"
        first_reviewed = client.post(
            f"/v1/domain-templates/{first.json()['id']}/review",
            headers=auth_headers(client, tenant["id"], user["id"]),
            json={
                "tenant_id": tenant["id"],
                "reviewer_user_id": user["id"],
                "decision": "approve",
            },
        )
        assert first_reviewed.status_code == 200, first_reviewed.text
        second = client.post(
            "/v1/domain-templates",
            json={
                "tenant_id": tenant["id"],
                "domain": "law_firm",
                "name": "Versioned Law Template",
                "version": "2.0.0",
                "compliance_profile": {"risk_level": "high"},
                "required_modules": ["human_review", "rag_with_citations"],
                "default_prompts": {"system": "v2"},
                "required_eval_cases": [
                    {"name": "review", "input": "send legal advice", "expected": {"review": True}}
                ],
            },
        )
        assert second.status_code == 200, second.text
        assert second.json()["status"] == "pending_review"

        active = client.get("/v1/domain-templates", params={"tenant_id": tenant["id"]}).json()
        versioned = [item for item in active if item["name"] == "Versioned Law Template"]
        assert len(versioned) == 1
        assert versioned[0]["version"] == "1.0.0"
        second_reviewed = client.post(
            f"/v1/domain-templates/{second.json()['id']}/review",
            headers=auth_headers(client, tenant["id"], user["id"]),
            json={
                "tenant_id": tenant["id"],
                "reviewer_user_id": user["id"],
                "decision": "approve",
            },
        )
        assert second_reviewed.status_code == 200, second_reviewed.text
        active = client.get("/v1/domain-templates", params={"tenant_id": tenant["id"]}).json()
        versioned = [item for item in active if item["name"] == "Versioned Law Template"]
        assert len(versioned) == 1
        assert versioned[0]["version"] == "2.0.0"
        old_detail = client.get(
            f"/v1/domain-templates/{first.json()['id']}",
            params={"tenant_id": tenant["id"]},
        )
        assert old_detail.status_code == 404

        feedback = client.post(
            "/v1/feedback",
            json={
                "tenant_id": tenant["id"],
                "user_id": user["id"],
                "rating": -1,
                "category": "template",
                "comment": "模板缺少更严格的利益冲突检查。",
            },
        )
        assert feedback.status_code == 200, feedback.text
        suggestions = client.get(
            f"/v1/domain-templates/{second.json()['id']}/improvement-suggestions",
            params={"tenant_id": tenant["id"]},
        )
        assert suggestions.status_code == 200, suggestions.text
        assert suggestions.json()["feedback_count"] >= 1
        assert suggestions.json()["suggestions"]

        archived = client.patch(
            f"/v1/domain-templates/{second.json()['id']}/status",
            headers=auth_headers(client, tenant["id"], user["id"]),
            json={"tenant_id": tenant["id"], "status": "archived"},
        )
        assert archived.status_code == 200, archived.text
        assert archived.json()["status"] == "archived"


def test_high_risk_domain_template_pending_list_and_reject() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase6 Review"}).json()
        owner = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "review-owner@example.com",
                "username": "review-owner",
                "role": "owner",
            },
        ).json()
        user = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "review-user@example.com",
                "username": "review-user",
                "role": "user",
            },
        ).json()
        template = client.post(
            "/v1/domain-templates",
            json={
                "tenant_id": tenant["id"],
                "domain": "hospital",
                "name": "Pending Hospital Template",
                "version": "1.0.0",
                "compliance_profile": {"risk_level": "high", "sensitive_data": ["PHI"]},
                "required_modules": ["human_review", "phi_privacy_filter"],
                "default_prompts": {"system": "pending"},
                "required_eval_cases": [],
            },
        )
        assert template.status_code == 200, template.text
        template_id = template.json()["id"]

        pending = client.get("/v1/domain-templates/pending", params={"tenant_id": tenant["id"]})
        assert pending.status_code == 200, pending.text
        assert any(item["id"] == template_id for item in pending.json())

        forbidden = client.post(
            f"/v1/domain-templates/{template_id}/review",
            headers=auth_headers(client, tenant["id"], user["id"]),
            json={
                "tenant_id": tenant["id"],
                "reviewer_user_id": user["id"],
                "decision": "approve",
            },
        )
        assert forbidden.status_code == 403

        rejected = client.post(
            f"/v1/domain-templates/{template_id}/review",
            headers=auth_headers(client, tenant["id"], owner["id"]),
            json={
                "tenant_id": tenant["id"],
                "reviewer_user_id": owner["id"],
                "decision": "reject",
                "comment": "Missing required eval cases.",
            },
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["status"] == "rejected"

        detail = client.get(f"/v1/domain-templates/{template_id}", params={"tenant_id": tenant["id"]})
        assert detail.status_code == 404
