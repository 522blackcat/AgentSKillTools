"""FastAPI service for production-style RAG access."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from rag_product.runtime import (
    build_rag_context_for_agent,
    ingest_knowledge_file,
    search_knowledge_base,
)


app = FastAPI(title="RAG Product Service", version="0.1.0")


class IngestRequest(BaseModel):
    file_path: str = Field(..., description="Local .txt or .md file path")


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class AgentContextResponse(BaseModel):
    query: str
    top_k: int
    context: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/rag/ingest")
def ingest(request: IngestRequest) -> dict[str, Any]:
    return ingest_knowledge_file(request.file_path)


@app.post("/rag/search")
def search(request: SearchRequest) -> dict[str, Any]:
    return search_knowledge_base(query=request.query, top_k=request.top_k)


@app.post("/rag/agent-context", response_model=AgentContextResponse)
def agent_context(request: SearchRequest) -> AgentContextResponse:
    context = build_rag_context_for_agent(query=request.query, top_k=request.top_k)
    return AgentContextResponse(
        query=request.query,
        top_k=request.top_k,
        context=context,
    )
