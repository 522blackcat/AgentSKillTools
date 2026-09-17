"""Tool call audit service."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ToolCall
from app.schemas import ToolCallCreate


TERMINAL_STATUSES = {"completed", "failed", "rejected", "cancelled"}


def record_tool_call(db: Session, data: ToolCallCreate) -> ToolCall:
    now = datetime.now(timezone.utc)
    call = ToolCall(
        tenant_id=data.tenant_id,
        run_id=data.run_id,
        tool_name=data.tool_name,
        risk_level=data.risk_level,
        status=data.status,
        input_summary=data.input_summary,
        output_summary=data.output_summary,
        error_json=data.error_json,
        metadata_json=data.metadata_json,
        started_at=now if data.status in {"running", *TERMINAL_STATUSES} else None,
        finished_at=now if data.status in TERMINAL_STATUSES else None,
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


def list_tool_calls(
    db: Session,
    tenant_id: str,
    run_id: str | None = None,
) -> list[ToolCall]:
    statement = (
        select(ToolCall)
        .where(ToolCall.tenant_id == tenant_id)
        .order_by(ToolCall.created_at)
    )
    if run_id:
        statement = statement.where(ToolCall.run_id == run_id)
    return list(db.scalars(statement).all())
