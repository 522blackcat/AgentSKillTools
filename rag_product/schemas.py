"""Data models for the local RAG training pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Document:
    doc_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    chunk: Chunk
    score: float


@dataclass(frozen=True)
class RagContext:
    query: str
    results: list[SearchResult]
    route: list[SearchResult] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        if not self.results:
            return "当前知识库没有检索到相关内容。"
        blocks = []
        for index, result in enumerate(self.results, start=1):
            source = result.chunk.metadata.get("source", result.chunk.doc_id)
            section = result.chunk.metadata.get("section_title", "")
            location = result.chunk.metadata.get("location", result.chunk.chunk_id)
            header = f"[{index}] source={source}; location={location}; score={result.score:.4f}"
            if section:
                header += f"; section={section}"
            blocks.append(
                f"{header}\n{result.chunk.text}"
            )
        return "\n\n".join(blocks)
