"""PostgreSQL + pgvector retrieval repository.

这个文件是生成项目中真正从向量数据库取匹配知识的入口。
本地没有 PostgreSQL 时可以通过传入 chunks 跑测试；生产运行时应调用 search_similar_chunks。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text

from app import settings
from app.rag.embedding import embed_query


HYBRID_SEARCH_SQL = """
select
    chunk_id,
    document_id,
    text as content,
    metadata_json ->> 'title' as source_title,
    metadata_json ->> 'source_uri' as source_uri,
    section_title,
    cast(metadata_json ->> 'page_number' as integer) as page_number,
    (embedding_vector <=> cast(:query_embedding as vector)) as vector_distance,
    ts_rank_cd(to_tsvector('simple', search_text), plainto_tsquery('simple', :query)) as keyword_rank,
    (
        (1 - (embedding_vector <=> cast(:query_embedding as vector))) * :vector_weight
        + ts_rank_cd(to_tsvector('simple', search_text), plainto_tsquery('simple', :query)) * :keyword_weight
    ) as hybrid_score
from document_chunks
where tenant_id = :tenant_id
  and knowledge_base_id = :knowledge_base_id
order by hybrid_score desc
limit :top_k
"""

VECTOR_SEARCH_SQL = HYBRID_SEARCH_SQL


def search_similar_chunks(
    tenant_id: str,
    knowledge_base_id: str,
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    if not tenant_id or not knowledge_base_id:
        return []
    if settings.DATABASE_URL.startswith("sqlite"):
        return []

    embedding = embed_query(query)
    vector_literal = "[" + ",".join(str(value) for value in embedding) + "]"
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as connection:
        rows = connection.execute(
            text(HYBRID_SEARCH_SQL),
            {
                "tenant_id": tenant_id,
                "knowledge_base_id": knowledge_base_id,
                "query_embedding": vector_literal,
                "query": query,
                "top_k": top_k,
                "vector_weight": 0.75,
                "keyword_weight": 0.25,
            },
        ).mappings()
        return [dict(row) for row in rows]
