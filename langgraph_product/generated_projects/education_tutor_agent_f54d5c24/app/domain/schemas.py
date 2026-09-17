"""Domain API schemas generated for this project."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


GENERATED_DOMAIN_ENTITIES = ['student', 'course', 'assignment', 'learning_plan']


class DomainRecordCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: str = "active"
    summary: str = ""
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class DomainRecordUpdate(BaseModel):
    tenant_id: str = Field(min_length=1)
    title: str | None = None
    status: str | None = None
    summary: str | None = None
    metadata_json: dict[str, Any] | None = None
