from fastapi.testclient import TestClient

from app.main import app


def test_generated_domain_profile_and_crud() -> None:
    with TestClient(app) as client:
        profile = client.get("/v1/domain/profile")
        assert profile.status_code == 200, profile.text
        assert profile.json()["domain_entities"]

        entities = client.get("/v1/domain/entities")
        assert entities.status_code == 200, entities.text
        assert "student" in entities.json()

        created = client.post(
            "/v1/domain/student",
            json={
                "tenant_id": "tenant-domain",
                "title": "Sample student",
                "summary": "Generated domain scaffold record.",
                "metadata_json": {"source": "test"},
            },
        )
        assert created.status_code == 200, created.text
        record = created.json()
        assert record["title"] == "Sample student"

        listed = client.get(
            "/v1/domain/student",
            params={"tenant_id": "tenant-domain"},
        )
        assert listed.status_code == 200, listed.text
        assert listed.json()[0]["id"] == record["id"]

        updated = client.patch(
            f"/v1/domain/student/{record['id']}",
            json={
                "tenant_id": "tenant-domain",
                "status": "review",
                "summary": "Updated generated domain record.",
            },
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["status"] == "review"
