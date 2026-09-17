"""Agent run persistence service.

Scaffold boundary for run history, traces, and status APIs.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AgentRun


def create_run(
    db: Session,
    tenant_id: str,
    user_id: str,
    graph_name: str,
    input_json: dict[str, Any],
) -> AgentRun:
    run = AgentRun(
        tenant_id=tenant_id,
        user_id=user_id or "anonymous",
        graph_name=graph_name,
        input_json=input_json,
        output_json={},
        status="created",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def finish_run(db: Session, run: AgentRun, output_json: dict[str, Any]) -> AgentRun:
    run.output_json = output_json
    run.status = "completed"
    db.commit()
    db.refresh(run)
    return run
