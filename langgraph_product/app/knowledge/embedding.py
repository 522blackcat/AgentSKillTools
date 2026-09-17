"""Embedding utilities.

Production path: provider embeddings stored in PostgreSQL pgvector.
Local fallback: deterministic hash embeddings stored as JSON.
"""

from __future__ import annotations

import hashlib
import math
import re


def embed_text(text: str, dimensions: int = 256) -> list[float]:
    vector = [0.0] * dimensions
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return dot / (left_norm * right_norm)


def lexical_score(query: str, text: str) -> float:
    query_terms = set(_tokens(query))
    if not query_terms:
        return 0.0
    text_terms = set(_tokens(text))
    return len(query_terms & text_terms) / len(query_terms)


def _tokens(text: str) -> list[str]:
    ascii_terms = re.findall(r"[a-zA-Z0-9_]{2,}", text.lower())
    cjk = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    cjk_bigrams: list[str] = []
    for term in cjk:
        cjk_bigrams.extend(term[index : index + 2] for index in range(len(term) - 1))
    return ascii_terms + cjk_bigrams
