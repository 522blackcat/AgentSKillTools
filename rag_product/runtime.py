"""Production-style runtime functions for agents and tools.

This file shows the shape a real agent project usually wants: small functions
that hide RAG internals and return stable, prompt-ready context.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from rag_product.pipeline import RagEngine


@lru_cache(maxsize=1)
def get_rag_engine() -> RagEngine:
    return RagEngine()


def search_knowledge_base(query: str, top_k: int = 5) -> dict[str, Any]:
    """Return structured retrieval results for app code or API clients."""
    context = get_rag_engine().search(query=query, top_k=top_k)
    return {
        "query": query,
        "top_k": top_k,
        "results": [
            {
                "score": result.score,
                "chunk_id": result.chunk.chunk_id,
                "doc_id": result.chunk.doc_id,
                "source": result.chunk.metadata.get("source", result.chunk.doc_id),
                "metadata": result.chunk.metadata,
                "text": result.chunk.text,
            }
            for result in context.results
        ],
    }


def build_rag_context_for_agent(query: str, top_k: int = 5) -> str:
    """Return prompt-ready RAG context for a LangGraph node or tool call."""
    return get_rag_engine().build_agent_context(query=query, top_k=top_k)


def ingest_knowledge_file(file_path: str) -> dict[str, Any]:
    """Ingest a local txt/md file into the configured vector store."""
    return get_rag_engine().ingest_file(file_path)
