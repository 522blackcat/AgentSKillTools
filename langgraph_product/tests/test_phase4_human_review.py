from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import auth_headers


def test_high_risk_builder_run_requires_human_review_and_approval() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase4"}).json()
        requester = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "requester@example.com",
                "username": "requester",
            },
        ).json()
        reviewer = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "reviewer@example.com",
                "username": "reviewer",
                "role": "reviewer",
            },
        ).json()
        session = client.post(
            "/v1/sessions",
            json={"tenant_id": tenant["id"], "user_id": requester["id"], "title": "review"},
        ).json()

        run = client.post(
            "/v1/chat/runs",
            json={
                "tenant_id": tenant["id"],
                "user_id": requester["id"],
                "session_id": session["id"],
                "message": "生成一个生产级律所 AI Agent",
            },
        ).json()
        invoked = client.post(
            f"/v1/chat/runs/{run['id']}/invoke",
            params={"tenant_id": tenant["id"]},
        )
        assert invoked.status_code == 200, invoked.text
        payload = invoked.json()
        assert payload["status"] == "awaiting_review"
        assert payload["output_json"]["review_required"] is True
        assert payload["output_json"]["review_request"]["status"] == "pending"

        pending = client.get("/v1/reviews/pending", params={"tenant_id": tenant["id"]})
        assert pending.status_code == 200, pending.text
        reviews = pending.json()
        assert len(reviews) == 1
        review_id = reviews[0]["id"]

        forbidden = client.post(
            f"/v1/reviews/{review_id}/decide",
            headers=auth_headers(client, tenant["id"], requester["id"]),
            json={
                "tenant_id": tenant["id"],
                "reviewer_user_id": requester["id"],
                "decision": "approve",
            },
        )
        assert forbidden.status_code == 403

        approved = client.post(
            f"/v1/reviews/{review_id}/decide",
            headers=auth_headers(client, tenant["id"], reviewer["id"]),
            json={
                "tenant_id": tenant["id"],
                "reviewer_user_id": reviewer["id"],
                "decision": "approve",
                "comment": "可以生成 blueprint。",
            },
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"
        assert approved.json()["run_status"] == "completed"
        messages = client.get(
            f"/v1/sessions/{session['id']}/messages",
            params={"tenant_id": tenant["id"]},
        )
        assert messages.status_code == 200, messages.text
        assert len(messages.json()) == 2
        events = client.get(
            f"/v1/chat/runs/{run['id']}/events",
            params={"tenant_id": tenant["id"]},
        )
        event_types = [item["event_type"] for item in events.json()]
        assert "review.pending" in event_types
        assert "review.decided" in event_types
        assert "run.completed.after_review" in event_types

        duplicate = client.post(
            f"/v1/reviews/{review_id}/decide",
            headers=auth_headers(client, tenant["id"], reviewer["id"]),
            json={
                "tenant_id": tenant["id"],
                "reviewer_user_id": reviewer["id"],
                "decision": "approve",
            },
        )
        assert duplicate.status_code == 400


def test_high_risk_builder_review_rejects_run() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase4 Reject"}).json()
        requester = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "reject-requester@example.com",
                "username": "reject-requester",
            },
        ).json()
        reviewer = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "reject-reviewer@example.com",
                "username": "reject-reviewer",
                "role": "admin",
            },
        ).json()
        run = client.post(
            "/v1/chat/runs",
            json={
                "tenant_id": tenant["id"],
                "user_id": requester["id"],
                "message": "生成一个生产级医院 AI Agent",
            },
        ).json()
        invoked = client.post(
            f"/v1/chat/runs/{run['id']}/invoke",
            params={"tenant_id": tenant["id"]},
        )
        assert invoked.status_code == 200, invoked.text
        review_id = invoked.json()["output_json"]["review_request"]["id"]

        rejected = client.post(
            f"/v1/reviews/{review_id}/decide",
            headers=auth_headers(client, tenant["id"], reviewer["id"]),
            json={
                "tenant_id": tenant["id"],
                "reviewer_user_id": reviewer["id"],
                "decision": "reject",
                "comment": "风险说明不足。",
            },
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["status"] == "rejected"
        assert rejected.json()["run_status"] == "rejected"

        fetched = client.get(
            f"/v1/chat/runs/{run['id']}",
            params={"tenant_id": tenant["id"]},
        )
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["output_json"]["final_answer"] == "人工审核已拒绝该高风险动作。"
