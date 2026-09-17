from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import auth_headers


def test_secure_token_grants_require_admin_or_owner_role() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase10 RBAC"}).json()
        user = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "phase10-user@example.com",
                "username": "phase10-user",
                "role": "user",
            },
        ).json()
        admin = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "phase10-admin@example.com",
                "username": "phase10-admin",
                "role": "admin",
            },
        ).json()
        payload = {
            "tenant_id": tenant["id"],
            "user_id": user["id"],
            "granted_tokens": 500,
            "reason": "test grant",
            "granted_by_user_id": admin["id"],
        }

        legacy = client.post("/v1/quotas/grants", json=payload)
        assert legacy.status_code == 410

        anonymous = client.post("/v1/secure/quotas/grants", json=payload)
        assert anonymous.status_code == 401

        forbidden = client.post(
            "/v1/secure/quotas/grants",
            headers=auth_headers(client, tenant["id"], user["id"]),
            json=payload,
        )
        assert forbidden.status_code == 403

        granted = client.post(
            "/v1/secure/quotas/grants",
            headers=auth_headers(client, tenant["id"], admin["id"]),
            json=payload,
        )
        assert granted.status_code == 200, granted.text
        assert granted.json()["remaining_tokens"] == 500


def test_model_registry_writes_require_admin_role() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase10 Models"}).json()
        user = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "phase10-model-user@example.com",
                "username": "phase10-model-user",
                "role": "user",
            },
        ).json()

        anonymous = client.post(
            "/v1/model-providers",
            json={"name": "anon_provider", "provider_type": "stub"},
        )
        assert anonymous.status_code == 401

        forbidden = client.post(
            "/v1/model-providers",
            headers=auth_headers(client, tenant["id"], user["id"]),
            json={"name": "user_provider", "provider_type": "stub"},
        )
        assert forbidden.status_code == 403
