"""Background job registry and optional RQ enqueue boundary."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import BackgroundJob
from app.schemas import BackgroundJobCreate


def create_background_job(db: Session, data: BackgroundJobCreate) -> BackgroundJob:
    job = BackgroundJob(
        tenant_id=data.tenant_id,
        job_type=data.job_type,
        payload=data.payload,
        created_by_user_id=data.created_by_user_id,
        max_attempts=data.max_attempts,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def list_background_jobs(db: Session, tenant_id: str) -> list[BackgroundJob]:
    return list(
        db.scalars(
            select(BackgroundJob)
            .where(BackgroundJob.tenant_id == tenant_id)
            .order_by(BackgroundJob.created_at)
        ).all()
    )


def get_background_job(db: Session, tenant_id: str, job_id: str) -> BackgroundJob:
    job = db.get(BackgroundJob, job_id)
    if job is None or job.tenant_id != tenant_id:
        raise ValueError("job not found")
    return job


def mark_job_running(db: Session, job: BackgroundJob) -> BackgroundJob:
    job.status = "running"
    job.attempts += 1
    job.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


def mark_job_finished(
    db: Session,
    job: BackgroundJob,
    status: str,
    result: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> BackgroundJob:
    job.status = status
    job.result = result or {}
    job.error_json = error
    job.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


def rq_settings() -> dict[str, str]:
    return {"redis_url": settings.redis_url, "queue_name": "agent-platform"}
