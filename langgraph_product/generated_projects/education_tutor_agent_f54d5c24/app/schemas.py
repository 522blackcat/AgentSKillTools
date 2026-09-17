"""Request schemas for generated agent APIs."""

from __future__ import annotations

from typing import Any
import base64

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    domain: str = "general"
    description: str = ""


class DocumentIngest(BaseModel):
    tenant_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    text: str = ""
    content_base64: str = ""
    content_bytes: bytes | None = None
    filename: str = ""
    source_uri: str = ""
    doc_type: str = "text"
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    def raw_bytes(self) -> bytes:
        if self.content_bytes is not None:
            return self.content_bytes
        if self.content_base64:
            return base64.b64decode(self.content_base64)
        return self.text.encode("utf-8")


class KnowledgeSearchRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class AgentInvokeRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    user_id: str = ""
    session_id: str | None = None
    message: str = Field(min_length=1)
    knowledge_base_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    risk_level: str = "low"
