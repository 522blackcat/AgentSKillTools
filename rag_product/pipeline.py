"""End-to-end local RAG pipeline."""

from __future__ import annotations

from rag_product.embeddings import EmbeddingClient, create_embedding_client
from rag_product.loaders import load_text_file
from rag_product.schemas import RagContext
from rag_product.settings import settings
from rag_product.splitters import split_document
from rag_product.vector_store import JsonVectorStore


class RagEngine:
    def __init__(
        self,
        embedding_client: EmbeddingClient | None = None,
        vector_store: JsonVectorStore | None = None,
    ):
        self.embedding_client = embedding_client or create_embedding_client()
        self.vector_store = vector_store or JsonVectorStore(settings.vector_store_path)

    def ingest_file(self, file_path: str) -> dict:
        document = load_text_file(file_path)
        chunks = split_document(document)
        vectors = self.embedding_client.embed([chunk.text for chunk in chunks])
        self.vector_store.upsert_chunks(chunks, vectors)
        section_count = sum(1 for chunk in chunks if chunk.metadata.get("chunk_type") == "section_summary")
        leaf_count = sum(1 for chunk in chunks if chunk.metadata.get("chunk_type") == "leaf")
        return {
            "doc_id": document.doc_id,
            "source": document.metadata["source"],
            "strategy": chunks[0].metadata["rag_strategy"] if chunks else "empty",
            "chunk_count": len(chunks),
            "section_count": section_count,
            "leaf_count": leaf_count,
        }

    def search(self, query: str, top_k: int | None = None) -> RagContext:
        query_vector = self.embedding_client.embed([query])[0]
        top_k = top_k or settings.top_k

        route = self.vector_store.search_filtered(
            query_vector=query_vector,
            top_k=max(3, top_k),
            metadata_filter={"chunk_type": "section_summary"},
            query_text=query,
        )
        if route:
            section_ids = {item.chunk.metadata["section_index"] for item in route[:3]}
            results = self.vector_store.search_filtered(
                query_vector=query_vector,
                top_k=top_k,
                metadata_filter={"chunk_type": "leaf", "section_index": section_ids},
                query_text=query,
            )
        else:
            results = self.vector_store.search_filtered(
                query_vector=query_vector,
                top_k=top_k,
                metadata_filter={"chunk_type": "leaf"},
                query_text=query,
            )
            if not results:
                results = self.vector_store.search_filtered(
                    query_vector=query_vector,
                    top_k=top_k,
                    query_text=query,
                )
        return RagContext(query=query, results=results, route=route)

    def build_agent_context(self, query: str, top_k: int | None = None) -> str:
        return self.search(query, top_k).to_prompt_context()
