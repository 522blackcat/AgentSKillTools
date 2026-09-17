from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import auth_headers


def test_tool_call_audit_requires_role_and_lists_by_run() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase13 Tools"}).json()
        user = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "phase13-user@example.com",
                "username": "phase13-user",
            },
        ).json()
        reviewer = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "phase13-reviewer@example.com",
                "username": "phase13-reviewer",
                "role": "reviewer",
            },
        ).json()
        run = client.post(
            "/v1/chat/runs",
            json={
                "tenant_id": tenant["id"],
                "user_id": user["id"],
                "message": "plan a tool",
            },
        ).json()

        anonymous = client.post(
            "/v1/tool-calls",
            json={
                "tenant_id": tenant["id"],
                "run_id": run["id"],
                "tool_name": "knowledge_search",
                "status": "completed",
                "input_summary": "search policy",
                "output_summary": "one citation",
            },
        )
        assert anonymous.status_code == 401

        created = client.post(
            "/v1/tool-calls",
            headers=auth_headers(client, tenant["id"], reviewer["id"]),
            json={
                "tenant_id": tenant["id"],
                "run_id": run["id"],
                "tool_name": "knowledge_search",
                "status": "completed",
                "input_summary": "search policy",
                "output_summary": "one citation",
                "metadata_json": {"timeout_seconds": 30},
            },
        )
        assert created.status_code == 200, created.text
        assert created.json()["status"] == "completed"
        assert created.json()["finished_at"] is not None

        listed = client.get(
            "/v1/tool-calls",
            headers=auth_headers(client, tenant["id"], reviewer["id"]),
            params={"tenant_id": tenant["id"], "run_id": run["id"]},
        )
        assert listed.status_code == 200, listed.text
        assert listed.json()[0]["tool_name"] == "knowledge_search"
        assert listed.json()[0]["metadata_json"]["timeout_seconds"] == 30
