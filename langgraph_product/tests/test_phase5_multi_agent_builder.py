from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import auth_headers


def test_builder_run_creates_multi_agent_blueprint_and_project_version() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase5"}).json()
        owner = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "owner@example.com",
                "username": "owner",
                "role": "owner",
            },
        ).json()
        run = client.post(
            "/v1/builder/runs",
            json={
                "tenant_id": tenant["id"],
                "user_id": owner["id"],
                "domain": "law_firm",
                "product_name": "Law Firm Agent",
                "requirements": "需要知识库问答、合同草稿、人审、审计、token 管控。",
            },
        ).json()
        invoked = client.post(
            f"/v1/builder/runs/{run['id']}/invoke",
            params={"tenant_id": tenant["id"]},
        )
        assert invoked.status_code == 200, invoked.text
        output = invoked.json()["output_json"]
        blueprint = output["agent_blueprint"]
        assert blueprint["domain"] == "law_firm"
        assert blueprint["validation"]["ok"] is True
        assert blueprint["validation"]["specialist_count"] >= 9
        agent_names = {agent["name"] for agent in blueprint["agents"]}
        assert "RAG Engineer Agent" in agent_names
        assert "Human Review Agent" in agent_names
        assert "Security Agent" in agent_names
        assert blueprint["memory"]["short_term"] == "chat_messages recent window"
        assert blueprint["database"]["vector_extension"] == "pgvector"
        assert output["review_request"]["status"] == "pending"

        events = client.get(
            f"/v1/chat/runs/{run['id']}/events",
            params={"tenant_id": tenant["id"]},
        )
        event_types = [item["event_type"] for item in events.json()]
        assert "builder.blueprint.created" in event_types

        approved = client.post(
            f"/v1/reviews/{output['review_request']['id']}/decide",
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
        assert generated_project["status"] == "blueprint_approved"
        assert generated_project["file_count"] >= 10
        assert generated_project["validation"]["status"] == "passed"
        assert generated_project["validation"]["failed"] == 0
        assert generated_project["eval_report"]["status"] == "passed"
        assert generated_project["eval_report"]["score"] == 1.0
        storage_path = Path(generated_project["storage_path"])
        assert (storage_path / "README.md").exists()
        assert (storage_path / "app" / "main.py").exists()
        assert (storage_path / "app" / "rag" / "service.py").exists()
        assert (storage_path / "tests" / "test_human_review.py").exists()

        versions = client.get(
            f"/v1/generated-projects/{generated_project['id']}/versions",
            params={"tenant_id": tenant["id"]},
        )
        assert versions.status_code == 200, versions.text
        assert versions.json()[0]["status"] == "approved"

        validations = client.get(
            f"/v1/generated-projects/{generated_project['id']}/validations",
            params={"tenant_id": tenant["id"]},
        )
        assert validations.status_code == 200, validations.text
        validation = validations.json()[0]
        assert validation["status"] == "passed"
        assert validation["summary"]["failed"] == 0
        assert any(check["name"] == "python_compile" for check in validation["checks"])
        sandbox_checks = [
            check for check in validation["checks"] if check["name"] == "sandbox_command"
        ]
        assert len(sandbox_checks) == 2
        assert all(check["ok"] for check in sandbox_checks)
        assert any("pytest tests" in check["detail"]["command"] for check in sandbox_checks)

        eval_reports = client.get(
            f"/v1/generated-projects/{generated_project['id']}/eval-reports",
            params={"tenant_id": tenant["id"]},
        )
        assert eval_reports.status_code == 200, eval_reports.text
        eval_report = eval_reports.json()[0]
        assert eval_report["status"] == "passed"
        assert eval_report["score"] == 1.0
        eval_names = {check["name"] for check in eval_report["checks"]}
        assert "rag_grounding" in eval_names
        assert "three_layer_memory" in eval_names
        assert "human_review_gates" in eval_names
        assert "runtime_validation" in eval_names

        final_events = client.get(
            f"/v1/chat/runs/{run['id']}/events",
            params={"tenant_id": tenant["id"]},
        )
        final_event_types = [item["event_type"] for item in final_events.json()]
        assert "project.validation.completed" in final_event_types
        assert "project.eval.completed" in final_event_types

        (storage_path / "app" / "main.py").write_text("def broken(:\n", encoding="utf-8")
        repaired = client.post(
            f"/v1/generated-projects/{generated_project['id']}/repair",
            params={"tenant_id": tenant["id"]},
            headers=auth_headers(client, tenant["id"], owner["id"]),
        )
        assert repaired.status_code == 200, repaired.text
        repair_payload = repaired.json()
        assert repair_payload["repaired"] is True
        assert repair_payload["version_number"] == 2
        assert repair_payload["validation"]["status"] == "passed"
        assert repair_payload["eval_report"]["status"] == "passed"

        repaired_versions = client.get(
            f"/v1/generated-projects/{generated_project['id']}/versions",
            params={"tenant_id": tenant["id"]},
        ).json()
        assert [item["version_number"] for item in repaired_versions] == [1, 2]
        assert repaired_versions[-1]["status"] == "repaired"

        repair_events = client.get(
            f"/v1/chat/runs/{run['id']}/events",
            params={"tenant_id": tenant["id"]},
        ).json()
        assert "project.repair.completed" in [item["event_type"] for item in repair_events]
