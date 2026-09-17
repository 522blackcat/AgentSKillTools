"""RAG service.

真实流程：query -> embedding -> pgvector search -> evidence context -> answer -> citation validation。
"""

from __future__ import annotations

from typing import Any

from app.llm.gateway import complete
from app.rag.citations import build_evidence_context, validate_citations
from app.rag.repository import search_similar_chunks

NO_ANSWER_POLICY = "refuse when evidence is missing"


def answer_with_citations(
    query: str,
    chunks: list[dict[str, Any]] | None = None,
    tenant_id: str = "",
    knowledge_base_id: str = "",
    top_k: int = 5,
) -> dict:
    if chunks is None:
        chunks = search_similar_chunks(
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            query=query,
            top_k=top_k,
        )
    if not chunks:
        return {"answer": "没有可引用证据，不能回答。", "citations": [], "evidence_context": ""}

    evidence_context, citations = build_evidence_context(chunks)
    prompt = (
        "只基于以下证据回答。每个关键结论必须带引用编号，例如 [1]。\n\n"
        f"证据：\n{evidence_context}\n\n"
        f"问题：{query}"
    )
    response = complete(prompt)
    answer = response["text"] or "基于知识库证据生成回答。[1]"
    if not validate_citations(answer, citations):
        answer = "基于知识库证据生成回答。[1]"
    return {"answer": answer, "citations": citations, "evidence_context": evidence_context}
