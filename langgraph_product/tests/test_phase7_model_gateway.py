from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database.models import TokenQuota, TokenUsageEvent
from app.database.session import SessionLocal
from app.main import app
from tests.helpers import auth_headers


def test_model_registry_defaults_and_custom_model_usage() -> None:
    with TestClient(app) as client:
        defaults = client.get("/v1/model-registry", params={"role": "cheap_chat"})
        assert defaults.status_code == 200, defaults.text
        assert defaults.json()
        tenant = client.post("/v1/tenants", json={"name": "Phase7 Model"}).json()
        admin = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "phase7-admin@example.com",
                "username": "phase7-admin",
                "role": "admin",
            },
        ).json()
        headers = auth_headers(client, tenant["id"], admin["id"])

        provider_name = f"local_test_provider_{uuid.uuid4().hex}"
        provider = client.post(
            "/v1/model-providers",
            headers=headers,
            json={
                "name": provider_name,
                "provider_type": "stub",
                "base_url": "http://localhost:9999/v1",
            },
        )
        assert provider.status_code == 200, provider.text
        model = client.post(
            "/v1/model-registry",
            headers=headers,
            json={
                "provider_id": provider.json()["id"],
                "model_id": "test-chat-model",
                "role": "cheap_chat",
                "context_window": 4096,
                "input_cost_per_1k": 2.0,
                "supports_tools": True,
            },
        )
        assert model.status_code == 200, model.text

        user = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "phase7-model@example.com",
                "username": "phase7-model",
            },
        ).json()
        run = client.post(
            "/v1/chat/runs",
            json={
                "tenant_id": tenant["id"],
                "user_id": user["id"],
                "message": "hello model gateway",
            },
        ).json()
        invoked = client.post(
            f"/v1/chat/runs/{run['id']}/invoke",
            params={"tenant_id": tenant["id"]},
        )
        assert invoked.status_code == 200, invoked.text
        usage = invoked.json()["output_json"]["token_usage"]
        assert usage["model_provider"] == provider_name
        assert usage["model_id"] == "test-chat-model"
        assert usage["estimated_cost"] > 0

        with SessionLocal() as db:
            event = db.scalars(
                select(TokenUsageEvent).where(TokenUsageEvent.run_id == run["id"])
            ).first()
            assert event is not None
            assert event.model_provider == provider_name
            assert event.model_id == "test-chat-model"
            assert float(event.estimated_cost) > 0


def test_runtime_blocks_when_user_quota_is_exhausted() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase7 Quota"}).json()
        user = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "phase7-quota@example.com",
                "username": "phase7-quota",
            },
        ).json()
        with SessionLocal() as db:
            quota = db.scalars(
                select(TokenQuota).where(
                    TokenQuota.tenant_id == tenant["id"],
                    TokenQuota.user_id == user["id"],
                )
            ).one()
            quota.token_limit = 1
            quota.token_used = 1
            db.commit()

        run = client.post(
            "/v1/chat/runs",
            json={
                "tenant_id": tenant["id"],
                "user_id": user["id"],
                "message": "this request should be blocked before model invocation",
            },
        ).json()
        invoked = client.post(
            f"/v1/chat/runs/{run['id']}/invoke",
            params={"tenant_id": tenant["id"]},
        )
        assert invoked.status_code == 200, invoked.text
        assert invoked.json()["status"] == "quota_exceeded"
        assert invoked.json()["output_json"]["quota"]["token_remaining"] == 0

        with SessionLocal() as db:
            event = db.scalars(
                select(TokenUsageEvent).where(TokenUsageEvent.run_id == run["id"])
            ).first()
            assert event is None


def test_model_gateway_falls_back_to_next_active_model() -> None:
    with TestClient(app) as client:
        admin_tenant = client.post("/v1/tenants", json={"name": "Phase7 Fallback Admin"}).json()
        admin = client.post(
            "/v1/users",
            json={
                "tenant_id": admin_tenant["id"],
                "email": "phase7-fallback-admin@example.com",
                "username": "phase7-fallback-admin",
                "role": "admin",
            },
        ).json()
        headers = auth_headers(client, admin_tenant["id"], admin["id"])
        fallback_provider_name = f"fallback_stub_{uuid.uuid4().hex}"
        fallback_provider = client.post(
            "/v1/model-providers",
            headers=headers,
            json={"name": fallback_provider_name, "provider_type": "stub"},
        )
        assert fallback_provider.status_code == 200, fallback_provider.text
        fallback_model = client.post(
            "/v1/model-registry",
            headers=headers,
            json={
                "provider_id": fallback_provider.json()["id"],
                "model_id": "fallback-chat-model",
                "role": "cheap_chat",
                "context_window": 4096,
            },
        )
        assert fallback_model.status_code == 200, fallback_model.text

        broken_provider = client.post(
            "/v1/model-providers",
            headers=headers,
            json={
                "name": f"broken_provider_{uuid.uuid4().hex}",
                "provider_type": "unsupported_for_test",
            },
        )
        assert broken_provider.status_code == 200, broken_provider.text
        broken_model = client.post(
            "/v1/model-registry",
            headers=headers,
            json={
                "provider_id": broken_provider.json()["id"],
                "model_id": "broken-chat-model",
                "role": "cheap_chat",
                "context_window": 4096,
            },
        )
        assert broken_model.status_code == 200, broken_model.text

        tenant = client.post("/v1/tenants", json={"name": "Phase7 Fallback"}).json()
        user = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "phase7-fallback@example.com",
                "username": "phase7-fallback",
            },
        ).json()
        run = client.post(
            "/v1/chat/runs",
            json={
                "tenant_id": tenant["id"],
                "user_id": user["id"],
                "message": "fallback should recover this request",
            },
        ).json()
        invoked = client.post(
            f"/v1/chat/runs/{run['id']}/invoke",
            params={"tenant_id": tenant["id"]},
        )
        assert invoked.status_code == 200, invoked.text
        usage = invoked.json()["output_json"]["token_usage"]
        assert usage["failed_over"] is True
        assert usage["model_provider"] == fallback_provider_name
        assert usage["model_id"] == "fallback-chat-model"
        assert usage["attempts"][0]["ok"] is False
        assert usage["attempts"][1]["ok"] is True

        with SessionLocal() as db:
            event = db.scalars(
                select(TokenUsageEvent).where(TokenUsageEvent.run_id == run["id"])
            ).first()
            assert event is not None
            assert event.metadata_json["failed_over"] is True
