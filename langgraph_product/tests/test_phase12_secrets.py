from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database.models import SecretRecord
from app.database.session import SessionLocal
from app.main import app
from app.secrets import get_secret_value
from tests.helpers import auth_headers


def test_secret_create_list_and_rotation_do_not_expose_plaintext() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase12 Secrets"}).json()
        admin = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "phase12-admin@example.com",
                "username": "phase12-admin",
                "role": "admin",
            },
        ).json()
        headers = auth_headers(client, tenant["id"], admin["id"])

        created = client.post(
            "/v1/secrets",
            headers=headers,
            json={
                "tenant_id": tenant["id"],
                "name": "OPENAI_API_KEY",
                "value": "sk-test-secret",
                "created_by_user_id": admin["id"],
            },
        )
        assert created.status_code == 200, created.text
        assert "sk-test-secret" not in created.text
        assert created.json()["version"] == 1

        rotated = client.post(
            "/v1/secrets",
            headers=headers,
            json={
                "tenant_id": tenant["id"],
                "name": "OPENAI_API_KEY",
                "value": "sk-test-secret-v2",
                "created_by_user_id": admin["id"],
            },
        )
        assert rotated.status_code == 200, rotated.text
        assert rotated.json()["version"] == 2
        assert "sk-test-secret-v2" not in rotated.text

        listed = client.get("/v1/secrets", headers=headers, params={"tenant_id": tenant["id"]})
        assert listed.status_code == 200, listed.text
        assert "sk-test-secret" not in listed.text
        assert [item["status"] for item in listed.json()] == ["rotated", "active"]

        with SessionLocal() as db:
            rows = list(
                db.scalars(
                    select(SecretRecord).where(SecretRecord.tenant_id == tenant["id"])
                ).all()
            )
            assert len(rows) == 2
            assert all("sk-test-secret" not in row.encrypted_value for row in rows)
            assert get_secret_value(db, tenant["id"], "OPENAI_API_KEY") == "sk-test-secret-v2"
