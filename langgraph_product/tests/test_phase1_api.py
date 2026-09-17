from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_create_user_run_and_token_usage() -> None:
    with TestClient(app) as client:
        run_api_flow(client)


def run_api_flow(client: TestClient) -> None:
    tenant_response = client.post("/v1/tenants", json={"name": "Acme"})
    assert tenant_response.status_code == 200
    tenant_id = tenant_response.json()["id"]

    user_response = client.post(
        "/v1/users",
        json={
            "tenant_id": tenant_id,
            "email": "user@example.com",
            "username": "user",
        },
    )
    assert user_response.status_code == 200
    user_id = user_response.json()["id"]

    session_response = client.post(
        "/v1/sessions",
        json={"tenant_id": tenant_id, "user_id": user_id, "title": "demo"},
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    run_response = client.post(
        "/v1/chat/runs",
        json={
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session_id,
            "message": "hello",
        },
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["id"]

    invoke_response = client.post(
        f"/v1/chat/runs/{run_id}/invoke",
        params={"tenant_id": tenant_id},
    )
    assert invoke_response.status_code == 200
    assert invoke_response.json()["status"] == "completed"

    usage_response = client.post(
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
    assert usage_response.status_code == 200
    assert usage_response.json()["total_tokens"] == 15

    quota_response = client.get(
        "/v1/quotas",
        params={"tenant_id": tenant_id, "user_id": user_id},
    )
    assert quota_response.status_code == 200
    assert quota_response.json()["token_used"] >= 15

    run_usage_response = client.get(
        f"/v1/token-usage/runs/{run_id}",
        params={"tenant_id": tenant_id},
    )
    assert run_usage_response.status_code == 200
    assert run_usage_response.json()["total_tokens"] >= 15
