from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_memory_and_rag_native_database_flow() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Phase3"}).json()
        user = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "phase3@example.com",
                "username": "phase3",
            },
        ).json()

        memory = client.post(
            "/v1/memories",
            json={
                "tenant_id": tenant["id"],
                "user_id": user["id"],
                "category": "preference",
                "memory_key": "language",
                "memory_value": "用户偏好中文回答",
            },
        )
        assert memory.status_code == 200, memory.text

        memory_search = client.get(
            "/v1/memories/search",
            params={
                "tenant_id": tenant["id"],
                "user_id": user["id"],
                "query": "用户喜欢什么语言",
            },
        )
        assert memory_search.status_code == 200, memory_search.text
        assert memory_search.json()[0]["key"] == "language"

        kb = client.post(
            "/v1/knowledge-bases",
            json={"tenant_id": tenant["id"], "name": "Law KB", "domain": "law_firm"},
        )
        assert kb.status_code == 200, kb.text
        kb_id = kb.json()["id"]

        document = client.post(
            f"/v1/knowledge-bases/{kb_id}/documents",
            json={
                "tenant_id": tenant["id"],
                "title": "律所 Agent 规则",
                "text": "# 人工审核\n\n法律意见输出必须由律师审核。\n\n# 引用\n\n回答必须保留资料来源。",
            },
        )
        assert document.status_code == 200, document.text
        assert document.json()["chunk_count"] >= 1

        search = client.post(
            f"/v1/knowledge-bases/{kb_id}/search",
            json={
                "tenant_id": tenant["id"],
                "query": "法律意见是否需要律师审核",
                "top_k": 3,
            },
        )
        assert search.status_code == 200, search.text
        assert "律师审核" in search.json()["results"][0]["text"]


def test_short_summary_and_long_term_memory_context() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Memory Layers"}).json()
        user = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "memory@example.com",
                "username": "memory",
            },
        ).json()
        session = client.post(
            "/v1/sessions",
            json={"tenant_id": tenant["id"], "user_id": user["id"], "title": "memory"},
        ).json()
        client.post(
            "/v1/memories",
            json={
                "tenant_id": tenant["id"],
                "user_id": user["id"],
                "category": "preference",
                "memory_key": "answer_language",
                "memory_value": "中文",
            },
        )

        for index in range(6):
            run = client.post(
                "/v1/chat/runs",
                json={
                    "tenant_id": tenant["id"],
                    "user_id": user["id"],
                    "session_id": session["id"],
                    "message": f"第 {index} 轮，请记住项目偏好",
                },
            ).json()
            invoked = client.post(
                f"/v1/chat/runs/{run['id']}/invoke",
                params={"tenant_id": tenant["id"]},
            )
            assert invoked.status_code == 200, invoked.text

        messages = client.get(
            f"/v1/sessions/{session['id']}/messages",
            params={"tenant_id": tenant["id"], "limit": 20},
        )
        assert messages.status_code == 200, messages.text
        assert len(messages.json()) >= 12

        context = client.get(
            f"/v1/sessions/{session['id']}/memory-context",
            params={
                "tenant_id": tenant["id"],
                "user_id": user["id"],
                "query": "回答语言偏好是什么",
            },
        )
        assert context.status_code == 200, context.text
        payload = context.json()
        assert payload["summary"]
        assert payload["recent_messages"]
        assert payload["long_term_memories"][0]["key"] == "answer_language"


def test_graph_rag_uses_knowledge_base_results() -> None:
    with TestClient(app) as client:
        tenant = client.post("/v1/tenants", json={"name": "Graph RAG"}).json()
        user = client.post(
            "/v1/users",
            json={
                "tenant_id": tenant["id"],
                "email": "graph-rag@example.com",
                "username": "graph-rag",
            },
        ).json()
        kb = client.post(
            "/v1/knowledge-bases",
            json={"tenant_id": tenant["id"], "name": "Agent KB", "domain": "law_firm"},
        ).json()
        client.post(
            f"/v1/knowledge-bases/{kb['id']}/documents",
            json={
                "tenant_id": tenant["id"],
                "title": "审核规则",
                "text": "# 审核\n\n法律意见必须先经过人工审核，然后才能对外发送。",
                "source_uri": "policy.md",
            },
        )
        run = client.post(
            "/v1/chat/runs",
            json={
                "tenant_id": tenant["id"],
                "user_id": user["id"],
                "message": "根据知识库回答：法律意见对外发送前需要什么？",
                "knowledge_base_id": kb["id"],
            },
        ).json()
        invoked = client.post(
            f"/v1/chat/runs/{run['id']}/invoke",
            params={"tenant_id": tenant["id"]},
        )
        assert invoked.status_code == 200, invoked.text
        output = invoked.json()["output_json"]
        assert output["rag_results"]
        assert "[1]" in output["final_answer"]
