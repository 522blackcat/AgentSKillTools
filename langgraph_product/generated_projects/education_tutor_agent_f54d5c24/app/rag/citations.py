"""Citation helpers for grounded RAG answers."""

from __future__ import annotations

from typing import Any


def build_evidence_context(chunks: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    citations = []
    lines = []
    for index, chunk in enumerate(chunks, start=1):
        citation_id = str(index)
        citation = {
            "citation_id": citation_id,
            "chunk_id": str(chunk.get("chunk_id", citation_id)),
            "document_id": chunk.get("document_id", ""),
            "source_title": chunk.get("source_title", ""),
            "source_uri": chunk.get("source_uri", ""),
            "section_title": chunk.get("section_title", ""),
            "page_number": chunk.get("page_number"),
        }
        citations.append(citation)
        lines.append(
            f"[{citation_id}] {citation['source_title']} "
            f"{citation['section_title']} p.{citation['page_number']}\n"
            f"{chunk.get('content', '')}"
        )
    return "\n\n".join(lines), citations


def validate_citations(answer: str, citations: list[dict[str, Any]]) -> bool:
    if not citations:
        return False
    allowed = {f"[{item['citation_id']}]" for item in citations}
    return any(token in answer for token in allowed)
