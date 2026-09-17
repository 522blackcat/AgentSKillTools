from fastapi.testclient import TestClient

from app import settings
from app.main import app


def test_document_ingestion_and_search_api() -> None:
    settings.MODEL_PROVIDER = "stub"
    with TestClient(app) as client:
        kb = client.post(
            "/v1/knowledge-bases",
            json={
                "tenant_id": "tenant-1",
                "name": "律所知识库",
                "domain": "law_firm",
                "description": "合同、案件和合规模板",
            },
        )
        assert kb.status_code == 200, kb.text
        kb_id = kb.json()["id"]

        ingested = client.post(
            f"/v1/knowledge-bases/{kb_id}/documents",
            json={
                "tenant_id": "tenant-1",
                "title": "合同审查指南",
                "text": "# 付款条款\n合同应写明付款期限、违约责任和争议解决方式。",
                "source_uri": "contract-review.md",
            },
        )
        assert ingested.status_code == 200, ingested.text
        assert ingested.json()["chunk_count"] >= 1

        searched = client.post(
            f"/v1/knowledge-bases/{kb_id}/search",
            json={"tenant_id": "tenant-1", "query": "付款期限", "top_k": 3},
        )
        assert searched.status_code == 200, searched.text
        assert searched.json()["results"]
        assert "付款期限" in searched.json()["results"][0]["text"]

        invoked = client.post(
            "/v1/agent/invoke",
            json={
                "tenant_id": "tenant-1",
                "message": "根据知识库回答付款期限风险",
                "knowledge_base_id": kb_id,
            },
        )
        assert invoked.status_code == 200, invoked.text
        assert invoked.json()["route"] == "rag"
        assert invoked.json()["citations"]


def test_raw_file_upload_and_document_versioning() -> None:
    with TestClient(app) as client:
        kb = client.post(
            "/v1/knowledge-bases",
            json={"tenant_id": "tenant-upload", "name": "Upload KB", "domain": "law_firm"},
        ).json()
        first = client.post(
            f"/v1/knowledge-bases/{kb['id']}/documents/upload",
            params={
                "tenant_id": "tenant-upload",
                "title": "争议解决条款",
                "filename": "dispute.md",
            },
            content=b"# clause\nUse arbitration or court jurisdiction clearly.",
            headers={"content-type": "application/octet-stream"},
        )
        assert first.status_code == 200, first.text
        assert first.json()["version"] == 1

        duplicate = client.post(
            f"/v1/knowledge-bases/{kb['id']}/documents/upload",
            params={
                "tenant_id": "tenant-upload",
                "title": "争议解决条款",
                "filename": "dispute.md",
            },
            content=b"# clause\nUse arbitration or court jurisdiction clearly.",
            headers={"content-type": "application/octet-stream"},
        )
        assert duplicate.status_code == 200, duplicate.text
        assert duplicate.json()["status"] == "duplicate_skipped"

        updated = client.post(
            f"/v1/knowledge-bases/{kb['id']}/documents/upload",
            params={
                "tenant_id": "tenant-upload",
                "title": "争议解决条款",
                "filename": "dispute.md",
            },
            content=b"# clause\nUse arbitration, court jurisdiction, and governing law clearly.",
            headers={"content-type": "application/octet-stream"},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["version"] == 2
        assert updated.json()["superseded_document_id"] == first.json()["document_id"]
