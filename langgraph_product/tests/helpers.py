from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings


def auth_headers(client: TestClient, tenant_id: str, user_id: str) -> dict[str, str]:
    issued = client.post(
        f"/v1/users/{user_id}/api-token",
        params={"tenant_id": tenant_id},
        headers={"X-Admin-Secret": settings.app_secret_key},
    )
    assert issued.status_code == 200, issued.text
    return {"Authorization": f"Bearer {issued.json()['api_token']}"}
