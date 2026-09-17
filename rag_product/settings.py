"""Environment settings for the RAG training project."""

from __future__ import annotations

import os
from dataclasses import dataclass


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(os.path.join(ROOT_DIR, ".env"))


@dataclass(frozen=True)
class RagSettings:
    embedding_provider: str = os.getenv("RAG_EMBEDDING_PROVIDER", "hash")
    embedding_model: str = os.getenv("RAG_EMBEDDING_MODEL", "nomic-embed-text")
    embedding_base_url: str = os.getenv("RAG_EMBEDDING_BASE_URL", "http://localhost:11434")
    embedding_api_key: str = os.getenv("RAG_EMBEDDING_API_KEY", "")
    vector_store_path: str = os.getenv(
        "RAG_VECTOR_STORE_PATH",
        os.path.join(ROOT_DIR, "rag_product", "rag_vector_store.json"),
    )
    top_k: int = int(os.getenv("RAG_TOP_K", "5"))


settings = RagSettings()
