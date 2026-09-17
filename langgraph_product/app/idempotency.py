"""Idempotency helpers for write APIs."""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import IdempotencyKey


def request_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_idempotent_response(
    db: Session,
    tenant_id: str,
    user_id: str,
    key: str | None,
    payload: str,
) -> dict[str, Any] | None:
    if not key:
        return None
    digest = request_hash(payload)
    statement = select(IdempotencyKey).where(
        IdempotencyKey.tenant_id == tenant_id,
        IdempotencyKey.user_id == user_id,
        IdempotencyKey.key == key,
    )
    record = db.scalars(statement).first()
    if record is None:
        return None
    if record.request_hash != digest:
        raise HTTPException(status_code=409, detail="idempotency key payload mismatch")
    if record.status == "completed":
        return record.response_json
    raise HTTPException(status_code=409, detail="idempotent request still in progress")


def save_idempotent_response(
    db: Session,
    tenant_id: str,
    user_id: str,
    key: str | None,
    payload: str,
    response: dict[str, Any],
) -> None:
    if not key:
        return
    record = IdempotencyKey(
        tenant_id=tenant_id,
        user_id=user_id,
        key=key,
        request_hash=request_hash(payload),
        response_json=response,
        status="completed",
    )
    db.add(record)
    db.commit()
