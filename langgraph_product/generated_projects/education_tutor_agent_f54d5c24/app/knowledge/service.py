"""Document ingestion, de-duplication, versioning, and hybrid retrieval."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.knowledge.loaders import load_document_text
from app.models import Document, DocumentChunk, KnowledgeBase, RetrievalLog
from app.rag.embedding import embed_query
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
    kb = db.get(KnowledgeBase, knowledge_base_id)
    if kb is None or kb.tenant_id != data.tenant_id:
        raise ValueError("knowledge base not found")

    payload = data.raw_bytes()
    text, detected_doc_type = load_document_text(data.filename, payload, data.text)
    if not text.strip():
        raise ValueError("document has no extractable text")
    checksum = hashlib.sha256(payload or text.encode("utf-8")).hexdigest()
    source_uri = data.source_uri or data.filename or data.title
    existing = latest_document(db, data.tenant_id, knowledge_base_id, source_uri)
    if existing is not None and existing.checksum == checksum:
        return {
            "document_id": existing.id,
            "chunk_count": 0,
            "checksum": checksum,
            "status": "duplicate_skipped",
            "version": existing.version,
        }
    version = (existing.version + 1) if existing is not None else 1
    if existing is not None:
        existing.status = "superseded"

    document = Document(
        tenant_id=data.tenant_id,
        knowledge_base_id=knowledge_base_id,
        title=data.title,
        source_uri=source_uri,
        doc_type=data.doc_type if data.doc_type != "text" else detected_doc_type,
        checksum=checksum,
        version=version,
        status="indexed",
        metadata_json=data.metadata_json,
    )
    db.add(document)
    db.flush()

    chunks = split_text(text)
    for index, chunk in enumerate(chunks, start=1):
        embedding = embed_query(chunk["text"])
        db.add(
            DocumentChunk(
                tenant_id=data.tenant_id,
                knowledge_base_id=knowledge_base_id,
                document_id=document.id,
                chunk_id=f"{document.id}-{index}",
                chunk_type="leaf",
                section_title=chunk["section_title"],
                location=chunk["location"],
                text=chunk["text"],
                search_text=f"{data.title}\n{chunk['section_title']}\n{chunk['text']}",
                embedding=embedding,
                metadata_json={
                    "source_uri": source_uri,
                    "title": data.title,
                    "version": version,
                    "embedding_vector_literal": "[" + ",".join(str(value) for value in embedding) + "]",
                },
            )
        )
    db.commit()
    return {
        "document_id": document.id,
        "chunk_count": len(chunks),
        "checksum": checksum,
        "status": document.status,
        "version": version,
        "superseded_document_id": existing.id if existing is not None else None,
    }


def search_knowledge_base(
    db: Session,
    knowledge_base_id: str,
    data: KnowledgeSearchRequest,
) -> dict[str, Any]:
    query_vector = embed_query(data.query)
    statement = select(DocumentChunk).where(
        DocumentChunk.tenant_id == data.tenant_id,
        DocumentChunk.knowledge_base_id == knowledge_base_id,
    )
    scored = []
    for chunk in db.scalars(statement).all():
        vector_score = cosine(query_vector, chunk.embedding)
        keyword_score = lexical_score(data.query, chunk.search_text or chunk.text)
        score = vector_score * 0.75 + keyword_score * 0.25
        scored.append((score, vector_score, keyword_score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    results = [
        {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "score": round(float(score), 6),
            "vector_score": round(float(vector_score), 6),
            "keyword_score": round(float(keyword_score), 6),
            "section_title": chunk.section_title,
            "location": chunk.location,
            "text": chunk.text,
            "metadata": chunk.metadata_json,
        }
        for score, vector_score, keyword_score, chunk in scored[: data.top_k]
    ]
    db.add(
        RetrievalLog(
            tenant_id=data.tenant_id,
            knowledge_base_id=knowledge_base_id,
            query=data.query,
            top_k=data.top_k,
            results=results,
        )
    )
    db.commit()
    return {"query": data.query, "top_k": data.top_k, "results": results}


def latest_document(
    db: Session,
    tenant_id: str,
    knowledge_base_id: str,
    source_uri: str,
) -> Document | None:
    if not source_uri:
        return None
    statement = (
        select(Document)
        .where(
            Document.tenant_id == tenant_id,
            Document.knowledge_base_id == knowledge_base_id,
            Document.source_uri == source_uri,
            Document.status == "indexed",
        )
        .order_by(Document.version.desc())
    )
    return db.scalars(statement).first()


def split_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[dict[str, str]]:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []
    sections = re.split(r"(?m)^#{1,6}\s+", normalized)
    chunks = []
    for section_index, section in enumerate(part.strip() for part in sections if part.strip()):
        title = first_line(section)
        body = section
        start = 0
        chunk_index = 0
        while start < len(body):
            end = min(len(body), start + chunk_size)
            chunk_text = body[start:end].strip()
            if chunk_text:
                chunks.append(
                    {
                        "section_title": title,
                        "location": f"section:{section_index + 1}:chunk:{chunk_index + 1}",
                        "text": chunk_text,
                    }
                )
            if end == len(body):
                break
            start = max(0, end - overlap)
            chunk_index += 1
    return chunks


def first_line(text: str) -> str:
    return text.splitlines()[0][:120] if text.splitlines() else ""


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def lexical_score(query: str, text: str) -> float:
    query_terms = set(re.findall(r"\w+", query.lower()))
    text_terms = set(re.findall(r"\w+", text.lower()))
    if not query_terms:
        return 0.0
    return len(query_terms & text_terms) / len(query_terms)
