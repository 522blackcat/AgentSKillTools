from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import auth_headers


def test_generated_law_project_includes_real_models_and_document_ingestion_api() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase15 Law"}).json()
        owner = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "phase15-owner@example.com",
                "username": "phase15-owner",
                "role": "owner",
            },
        ).json()
        run = client.post(
            "/v1/builder/runs",
            json={
                "tenant_id": tenant["id"],
                "user_id": owner["id"],
                "domain": "law_firm",
                "product_name": "Law Firm Agent Fresh",
                "requirements": "生成律所 AI Agent，必须包含 RAG 文件、真实数据库模型、文档入库 API。",
            },
        ).json()
        invoked = client.post(
            f"/v1/builder/runs/{run['id']}/invoke",
            params={"tenant_id": tenant["id"]},
        )
        assert invoked.status_code == 200, invoked.text
        output = invoked.json()["output_json"]

        approved = client.post(
            f"/v1/reviews/{output['review_request']['id']}/decide",
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
        storage_path = Path(project["storage_path"])
        assert project["validation"]["status"] == "passed"
        assert project["eval_report"]["status"] == "passed"
        assert (storage_path / "app" / "rag" / "service.py").exists()
        assert (storage_path / "app" / "rag" / "repository.py").exists()
        assert (storage_path / "app" / "knowledge" / "loaders.py").exists()
        assert (storage_path / "app" / "knowledge" / "service.py").exists()
        assert (storage_path / "app" / "schemas.py").exists()
        assert (
            storage_path / "alembic" / "versions" / "0001_initial_pgvector_schema.py"
        ).exists()
        assert (storage_path / "tests" / "test_ingestion_api.py").exists()

        models = (storage_path / "app" / "models.py").read_text(encoding="utf-8")
        main = (storage_path / "app" / "main.py").read_text(encoding="utf-8")
        repository = (storage_path / "app" / "rag" / "repository.py").read_text(encoding="utf-8")
        migration = (
            storage_path / "alembic" / "versions" / "0001_initial_pgvector_schema.py"
        ).read_text(encoding="utf-8")
        knowledge_service = (storage_path / "app" / "knowledge" / "service.py").read_text(
            encoding="utf-8"
        )
        assert "class KnowledgeBase(Base)" in models
        assert "class Document(Base)" in models
        assert "class DocumentChunk(Base)" in models
        assert "class RetrievalLog(Base)" in models
        assert '@app.post("/v1/knowledge-bases")' in main
        assert '@app.post("/v1/knowledge-bases/{knowledge_base_id}/documents")' in main
        assert '@app.post("/v1/knowledge-bases/{knowledge_base_id}/documents/upload")' in main
        assert '@app.post("/v1/agent/invoke")' in main
        assert "def ingest_document" in knowledge_service
        assert "def search_knowledge_base" in knowledge_service
        assert "def latest_document" in knowledge_service
        assert "duplicate_skipped" in knowledge_service
        assert "HYBRID_SEARCH_SQL" in repository
        assert "ts_rank_cd" in repository
        assert "create extension if not exists vector" in migration
        assert "embedding_vector vector(8)" in migration
        assert "to_tsvector" in migration
