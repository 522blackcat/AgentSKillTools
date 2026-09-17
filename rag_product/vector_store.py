"""Small JSON vector store for local RAG learning."""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any

from rag_product.schemas import Chunk, SearchResult


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return dot / (left_norm * right_norm)


class JsonVectorStore:
    def __init__(self, path: str):
        self.path = path
        self.records: list[dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.path):
            self.records = []
            return
        with open(self.path, "r", encoding="utf-8") as f:
            self.records = json.load(f)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)

    def upsert_chunks(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        by_id = {record["chunk"]["chunk_id"]: record for record in self.records}
        for chunk, vector in zip(chunks, vectors):
            by_id[chunk.chunk_id] = {
                "chunk": {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "text": chunk.text,
                    "metadata": chunk.metadata,
                },
                "vector": vector,
            }
        self.records = list(by_id.values())
        self.save()

    def search(self, query_vector: list[float], top_k: int) -> list[SearchResult]:
        return self.search_filtered(query_vector=query_vector, top_k=top_k)

    def search_filtered(
        self,
        query_vector: list[float],
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
        query_text: str = "",
    ) -> list[SearchResult]:
        scored = []
        for record in self.records:
            data = record["chunk"]
            metadata = data.get("metadata", {})
            if metadata_filter and not _metadata_matches(metadata, metadata_filter):
                continue
            score = cosine_similarity(query_vector, record["vector"])
            if query_text:
                score += lexical_overlap_score(query_text, data["text"]) * 0.15
            scored.append(
                SearchResult(
                    chunk=Chunk(
                        chunk_id=data["chunk_id"],
                        doc_id=data["doc_id"],
                        text=data["text"],
                        metadata=metadata,
                    ),
                    score=score,
                )
            )
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]


def lexical_overlap_score(query: str, text: str) -> float:
    query_terms = set(_terms(query))
    if not query_terms:
        return 0.0
    text_terms = set(_terms(text))
    if not text_terms:
        return 0.0
    return len(query_terms & text_terms) / len(query_terms)


def _terms(text: str) -> list[str]:
    ascii_terms = re.findall(r"[a-zA-Z0-9_]{2,}", text.lower())
    cjk_terms = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    cjk_bigrams = []
    for term in cjk_terms:
        cjk_bigrams.extend(term[index : index + 2] for index in range(len(term) - 1))
    return ascii_terms + cjk_bigrams


def _metadata_matches(metadata: dict[str, Any], expected: dict[str, Any]) -> bool:
    for key, value in expected.items():
        if isinstance(value, set):
            if metadata.get(key) not in value:
                return False
        elif metadata.get(key) != value:
            return False
    return True
