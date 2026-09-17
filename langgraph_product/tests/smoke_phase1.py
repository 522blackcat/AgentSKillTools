from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    with TestClient(app) as client:
        run_smoke(client)


def run_smoke(client: TestClient) -> None:
    health = client.get("/healthz")
    assert health.status_code == 200, health.text

    tenant = client.post("/v1/tenants", json={"name": "Smoke"})
    assert tenant.status_code == 200, tenant.text
    tenant_id = tenant.json()["id"]

    user = client.post(
        "/v1/users",
        json={"tenant_id": tenant_id, "email": "smoke@example.com", "username": "smoke"},
    )
    assert user.status_code == 200, user.text
    user_id = user.json()["id"]

    session = client.post(
        "/v1/sessions",
        json={"tenant_id": tenant_id, "user_id": user_id, "title": "smoke"},
    )
    assert session.status_code == 200, session.text

    run = client.post(
        "/v1/chat/runs",
        headers={"Idempotency-Key": "smoke-chat-run"},
        json={
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session.json()["id"],
            "message": "hello",
        },
    )
    assert run.status_code == 200, run.text
    run_id = run.json()["id"]
    duplicate_run = client.post(
        "/v1/chat/runs",
        headers={"Idempotency-Key": "smoke-chat-run"},
        json={
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session.json()["id"],
            "message": "hello",
        },
    )
    assert duplicate_run.status_code == 200, duplicate_run.text
    assert duplicate_run.json()["id"] == run_id

    invoked = client.post(f"/v1/chat/runs/{run_id}/invoke", params={"tenant_id": tenant_id})
    assert invoked.status_code == 200, invoked.text
    assert invoked.json()["status"] == "completed"

    usage = client.post(
        "/v1/token-usage",
        json={
            "tenant_id": tenant_id,
            "user_id": user_id,
            "run_id": run_id,
            "call_type": "chat_completion",
            "prompt_tokens": 10,
            "completion_tokens": 5,
        },
    )
    assert usage.status_code == 200, usage.text
    assert usage.json()["total_tokens"] == 15

    quota = client.get("/v1/quotas", params={"tenant_id": tenant_id, "user_id": user_id})
    assert quota.status_code == 200, quota.text
    assert quota.json()["token_used"] >= 15

    template = client.post(
        "/v1/domain-templates",
        json={
            "domain": "law_firm",
            "name": "Law Firm Agent",
            "required_modules": ["rag", "human_review"],
        },
    )
    assert template.status_code == 200, template.text

    project = client.post(
        "/v1/generated-projects",
        json={
            "tenant_id": tenant_id,
            "owner_user_id": user_id,
            "name": "law-agent",
            "domain": "law_firm",
            "blueprint": {"name": "law-agent"},
        },
    )
    assert project.status_code == 200, project.text
    project_id = project.json()["id"]
    version_id = project.json()["active_version_id"]

    versions = client.get(
        f"/v1/generated-projects/{project_id}/versions",
        params={"tenant_id": tenant_id},
    )
    assert versions.status_code == 200, versions.text
    assert versions.json()[0]["id"] == version_id

    feedback = client.post(
        "/v1/feedback",
        json={"tenant_id": tenant_id, "user_id": user_id, "run_id": run_id, "rating": 1},
    )
    assert feedback.status_code == 200, feedback.text

    print("phase1 smoke passed")


if __name__ == "__main__":
    main()
