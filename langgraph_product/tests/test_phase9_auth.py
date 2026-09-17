from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_user_api_token_requires_admin_secret_and_supports_whoami() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase9 Auth"}).json()
        user = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "phase9-auth@example.com",
                "username": "phase9-auth",
                "role": "admin",
            },
        ).json()

        denied = client.post(
            f"/v1/users/{user['id']}/api-token",
            params={"tenant_id": tenant["id"]},
        )
        assert denied.status_code == 401

        issued = client.post(
            f"/v1/users/{user['id']}/api-token",
            params={"tenant_id": tenant["id"]},
            headers={"X-Admin-Secret": settings.app_secret_key},
        )
        assert issued.status_code == 200, issued.text
        token = issued.json()["api_token"]
        assert token.startswith("agt_")

        whoami = client.get("/v1/auth/whoami", headers={"Authorization": f"Bearer {token}"})
        assert whoami.status_code == 200, whoami.text
        assert whoami.json()["id"] == user["id"]
        assert whoami.json()["role"] == "admin"

        rejected = client.get("/v1/auth/whoami", headers={"Authorization": "Bearer bad"})
        assert rejected.status_code == 401
