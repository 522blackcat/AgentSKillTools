"""Embedding boundary for RAG retrieval.

生产项目应在这里接真实 embedding provider。本地测试使用确定性向量，保证不依赖网络。
"""

from __future__ import annotations

import hashlib


EMBEDDING_DIMENSIONS = 8


def embed_query(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = []
    for index in range(EMBEDDING_DIMENSIONS):
        raw = digest[index] / 255
        values.append(round(raw, 6))
    return values
