from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import auth_headers


def test_background_job_registry_requires_admin_and_tracks_status() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase14 Jobs"}).json()
        admin = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "phase14-admin@example.com",
                "username": "phase14-admin",
                "role": "admin",
            },
        ).json()
        headers = auth_headers(client, tenant["id"], admin["id"])

        anonymous = client.post(
            "/v1/jobs",
            json={
                "tenant_id": tenant["id"],
                "job_type": "document_ingest",
                "payload": {"document_id": "doc-1"},
                "created_by_user_id": admin["id"],
            },
        )
        assert anonymous.status_code == 401

        created = client.post(
            "/v1/jobs",
            headers=headers,
            json={
                "tenant_id": tenant["id"],
                "job_type": "document_ingest",
                "payload": {"document_id": "doc-1"},
                "created_by_user_id": admin["id"],
            },
        )
        assert created.status_code == 200, created.text
        assert created.json()["status"] == "queued"
        assert created.json()["rq"]["queue_name"] == "agent-platform"

        listed = client.get("/v1/jobs", headers=headers, params={"tenant_id": tenant["id"]})
        assert listed.status_code == 200, listed.text
        assert listed.json()[0]["job_type"] == "document_ingest"

        detail = client.get(
            f"/v1/jobs/{created.json()['id']}",
            headers=headers,
            params={"tenant_id": tenant["id"]},
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["payload"]["document_id"] == "doc-1"
