"""RAG engineering training project.

This package is intentionally independent from langgraph_product. It teaches
the core RAG pipeline first, then the mature ideas can be rewritten into the
final LangGraph agent project.
"""

from rag_product.pipeline import RagEngine

__all__ = ["RagEngine"]
