from app import settings
from app.rag.citations import build_evidence_context, validate_citations
from app.rag.embedding import embed_query
from app.rag.repository import VECTOR_SEARCH_SQL, search_similar_chunks
from app.rag.service import answer_with_citations


def test_rag_no_answer() -> None:
    result = answer_with_citations("q", [])
    assert result["citations"] == []


def test_embedding_is_deterministic() -> None:
    assert embed_query("contract") == embed_query("contract")


def test_vector_sql_contains_pgvector_distance() -> None:
    assert "embedding_vector <=>" in VECTOR_SEARCH_SQL
    assert "ts_rank_cd" in VECTOR_SEARCH_SQL
    assert "tenant_id" in VECTOR_SEARCH_SQL
    assert "knowledge_base_id" in VECTOR_SEARCH_SQL


def test_repository_local_without_ids_returns_empty() -> None:
    settings.DATABASE_URL = "sqlite:///agent.db"
    assert search_similar_chunks("", "", "query") == []


def test_citation_context_and_validation() -> None:
    context, citations = build_evidence_context(
        [
            {
                "chunk_id": "c1",
                "document_id": "d1",
                "content": "合同应约定违约责任。",
                "source_title": "合同审查指南",
                "section_title": "违约责任",
                "page_number": 3,
            }
        ]
    )
    assert "[1]" in context
    assert citations[0]["chunk_id"] == "c1"
    assert validate_citations("需要补充违约责任。[1]", citations)


def test_rag_uses_provided_chunks_with_citations() -> None:
    settings.MODEL_PROVIDER = "stub"
    result = answer_with_citations(
        "合同风险是什么",
        [
            {
                "chunk_id": "c1",
                "document_id": "d1",
                "content": "合同缺少付款期限。",
                "source_title": "合同",
                "section_title": "付款",
                "page_number": 1,
            }
        ],
    )
    assert result["citations"][0]["citation_id"] == "1"
    assert "[1]" in result["answer"]
