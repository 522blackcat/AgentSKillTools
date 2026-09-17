"""RAG 知识库和检索服务。

本地版本把 document、chunk、retrieval log 放在数据库中。
生产设计保留 PostgreSQL + pgvector 和真实 embedding provider。
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Document, DocumentChunk, KnowledgeBase, RetrievalLog
from app.knowledge.embedding import cosine, embed_text, lexical_score
from app.knowledge.splitter import split_text
from app.schemas import DocumentIngest, KnowledgeBaseCreate, KnowledgeSearchRequest


def create_knowledge_base(db: Session, data: KnowledgeBaseCreate) -> KnowledgeBase:
    kb = KnowledgeBase(
        tenant_id=data.tenant_id,
        name=data.name,
        domain=data.domain,
        description=data.description,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def ingest_document(db: Session, knowledge_base_id: str, data: DocumentIngest) -> dict[str, Any]:
    checksum = hashlib.sha256(data.text.encode("utf-8")).hexdigest()
    document = Document(
        tenant_id=data.tenant_id,
        knowledge_base_id=knowledge_base_id,
        title=data.title,
        source_uri=data.source_uri,
        doc_type=data.doc_type,
        checksum=checksum,
        metadata_json=data.metadata_json,
    )
    db.add(document)
    db.flush()
    chunks = split_text(data.text)
    for item in chunks:
        chunk_id = f"{document.id}-{item['section_index']}-{item['chunk_index']}"
        db.add(
            DocumentChunk(
                tenant_id=data.tenant_id,
                knowledge_base_id=knowledge_base_id,
                document_id=document.id,
                chunk_id=chunk_id,
                chunk_type="leaf",
                section_title=item["section_title"],
                location=item["location"],
                text=item["text"],
                embedding=embed_text(item["text"]),
                metadata_json={"source_uri": data.source_uri, "title": data.title},
            )
        )
    db.commit()
    return {"document_id": document.id, "chunk_count": len(chunks), "checksum": checksum}


def search_knowledge_base(
    db: Session,
    knowledge_base_id: str,
    data: KnowledgeSearchRequest,
) -> dict[str, Any]:
    query_vector = embed_text(data.query)
    statement = select(DocumentChunk).where(
        DocumentChunk.tenant_id == data.tenant_id,
        DocumentChunk.knowledge_base_id == knowledge_base_id,
    )
    scored = []
    for chunk in db.scalars(statement).all():
        vector_score = cosine(query_vector, chunk.embedding)
        keyword_score = lexical_score(data.query, chunk.text)
        score = vector_score + keyword_score * 0.2
        scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    results = [
        {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "score": score,
            "section_title": chunk.section_title,
            "location": chunk.location,
            "text": chunk.text,
            "metadata": chunk.metadata_json,
        }
        for score, chunk in scored[: data.top_k]
    ]
    db.add(
        RetrievalLog(
            tenant_id=data.tenant_id,
            run_id=data.run_id,
            knowledge_base_id=knowledge_base_id,
            query=data.query,
            rewritten_query=data.query,
            top_k=data.top_k,
            results=results,
        )
    )
    db.commit()
    return {"query": data.query, "top_k": data.top_k, "results": results}


def build_rag_context(results: list[dict]) -> str:
    if not results:
        return ""
    blocks = []
    for index, result in enumerate(results, start=1):
        metadata = result.get("metadata", {})
        source = metadata.get("source_uri") or metadata.get("title") or result.get("document_id")
        blocks.append(
            f"[{index}] source={source}; section={result.get('section_title', '')}; "
            f"location={result.get('location', '')}; score={result.get('score', 0):.4f}\n"
            f"{result.get('text', '')}"
        )
    return "\n\n".join(blocks)
