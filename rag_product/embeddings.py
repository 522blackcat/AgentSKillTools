"""Embedding clients used by the local RAG training project."""

from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod

from rag_product.settings import RagSettings, settings


class EmbeddingClient(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class HashEmbeddingClient(EmbeddingClient):
    """Dependency-free fallback for learning retrieval mechanics."""

    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class OllamaEmbeddingClient(EmbeddingClient):
    def __init__(self, config: RagSettings = settings):
        self.config = config

    def embed(self, texts: list[str]) -> list[list[float]]:
        import requests

        vectors = []
        url = self.config.embedding_base_url.rstrip("/") + "/api/embeddings"
        for text in texts:
            response = requests.post(
                url,
                json={"model": self.config.embedding_model, "prompt": text},
                timeout=60,
            )
            response.raise_for_status()
            vectors.append(response.json()["embedding"])
        return vectors


class OpenAIEmbeddingClient(EmbeddingClient):
    def __init__(self, config: RagSettings = settings):
        from openai import OpenAI

        self.config = config
        self.client = OpenAI(
            api_key=config.embedding_api_key or "EMPTY",
            base_url=config.embedding_base_url,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(
            model=self.config.embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]


def create_embedding_client(config: RagSettings = settings) -> EmbeddingClient:
    provider = config.embedding_provider.lower()
    if provider == "ollama":
        return OllamaEmbeddingClient(config)
    if provider in {"openai", "openai_compatible"}:
        return OpenAIEmbeddingClient(config)
    return HashEmbeddingClient()
