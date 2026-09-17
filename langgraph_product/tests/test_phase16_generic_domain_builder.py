from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import auth_headers


def test_builder_generates_dynamic_domain_profile_and_domain_scaffold() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase16 Ecommerce"}).json()
        owner = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "phase16-owner@example.com",
                "username": "phase16-owner",
                "role": "owner",
            },
        ).json()
        run = client.post(
            "/v1/builder/runs",
            json={
                "tenant_id": tenant["id"],
                "user_id": owner["id"],
                "domain": "ecommerce",
                "product_name": "Ecommerce Support Agent",
                "requirements": "生成电商客服 AI Agent，处理订单查询、退款、商品推荐和工单升级。",
            },
        ).json()
        invoked = client.post(
            f"/v1/builder/runs/{run['id']}/invoke",
            params={"tenant_id": tenant["id"]},
        )
        assert invoked.status_code == 200, invoked.text
        blueprint = invoked.json()["output_json"]["agent_blueprint"]
        profile = blueprint["domain_profile"]
        entity_names = {entity["name"] for entity in profile["domain_entities"]}
        assert {"product", "order", "refund", "support_ticket"}.issubset(entity_names)
        assert any(tool["name"] == "product_lookup" for tool in profile["domain_tools"])

        if invoked.json()["output_json"].get("review_request"):
            approved = client.post(
                f"/v1/reviews/{invoked.json()['output_json']['review_request']['id']}/decide",
                headers=auth_headers(client, tenant["id"], owner["id"]),
                json={
                    "tenant_id": tenant["id"],
                    "reviewer_user_id": owner["id"],
                    "decision": "approve",
                },
            )
            assert approved.status_code == 200, approved.text

        fetched = client.get(
            f"/v1/chat/runs/{run['id']}",
            params={"tenant_id": tenant["id"]},
        )
        project = fetched.json()["output_json"]["generated_project"]
        assert project["validation"]["status"] == "passed"
        storage_path = Path(project["storage_path"])
        assert storage_path.name.startswith("ecommerce_support_agent_")
        domain_models = (storage_path / "app" / "domain" / "models.py").read_text(
            encoding="utf-8"
        )
        domain_routes = (storage_path / "app" / "domain" / "routes.py").read_text(
            encoding="utf-8"
        )
        tools = (storage_path / "app" / "tools" / "registry.py").read_text(encoding="utf-8")
        assert "class Product(Base)" in domain_models
        assert "class Order(Base)" in domain_models
        assert "class Refund(Base)" in domain_models
        assert "class SupportTicket(Base)" in domain_models
        assert (storage_path / "app" / "agents" / "supervisor.py").exists()
        assert (storage_path / "app" / "agents" / "state.py").exists()
        assert (storage_path / "app" / "runs" / "service.py").exists()
        assert (storage_path / "app" / "reviews" / "service.py").exists()
        assert (storage_path / "app" / "evals" / "runner.py").exists()
        assert (storage_path / "app" / "prompts" / "router.md").exists()
        assert (storage_path / "app" / "prompts" / "tool_planner.md").exists()
        assert (storage_path / "app" / "prompts" / "memory_extract.md").exists()
        assert (storage_path / "tests" / "test_project_structure.py").exists()
        assert '"/v1/domain"' in domain_routes
        assert "product_lookup" in tools
        assert "support_ticket_lookup" in tools
