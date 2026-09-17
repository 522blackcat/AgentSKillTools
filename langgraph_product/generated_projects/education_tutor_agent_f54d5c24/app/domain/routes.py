"""Generated domain CRUD routes.

These routes are intentionally conservative scaffold code. They give the generated
project real domain tables and APIs while keeping business rules easy to replace.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.domain.models import ENTITY_MODELS
from app.domain.schemas import DomainRecordCreate, DomainRecordUpdate


DOMAIN_PROFILE = {'industry': 'Education', 'risk_level': 'medium', 'primary_users': ['teacher', 'student', 'academic_admin'], 'core_workflows': ['answer_course_questions', 'grade_with_review', 'recommend_learning_plan', 'track_progress'], 'domain_entities': [{'name': 'student', 'class_name': 'Student', 'table_name': 'domain_students', 'display_name': 'student', 'fields': [{'name': 'title', 'type': 'str', 'required': True}, {'name': 'status', 'type': 'str', 'required': False}, {'name': 'summary', 'type': 'str', 'required': False}, {'name': 'metadata_json', 'type': 'dict', 'required': False}]}, {'name': 'course', 'class_name': 'Course', 'table_name': 'domain_courses', 'display_name': 'course', 'fields': [{'name': 'title', 'type': 'str', 'required': True}, {'name': 'status', 'type': 'str', 'required': False}, {'name': 'summary', 'type': 'str', 'required': False}, {'name': 'metadata_json', 'type': 'dict', 'required': False}]}, {'name': 'assignment', 'class_name': 'Assignment', 'table_name': 'domain_assignments', 'display_name': 'assignment', 'fields': [{'name': 'title', 'type': 'str', 'required': True}, {'name': 'status', 'type': 'str', 'required': False}, {'name': 'summary', 'type': 'str', 'required': False}, {'name': 'metadata_json', 'type': 'dict', 'required': False}]}, {'name': 'learning_plan', 'class_name': 'LearningPlan', 'table_name': 'domain_learning_plans', 'display_name': 'learning plan', 'fields': [{'name': 'title', 'type': 'str', 'required': True}, {'name': 'status', 'type': 'str', 'required': False}, {'name': 'summary', 'type': 'str', 'required': False}, {'name': 'metadata_json', 'type': 'dict', 'required': False}]}], 'domain_tools': [{'name': 'student_lookup', 'risk': 'medium', 'review_required': False, 'input_schema': {'query': 'string', 'tenant_id': 'string'}, 'description': 'Lookup student records for the generated domain.'}, {'name': 'course_lookup', 'risk': 'medium', 'review_required': False, 'input_schema': {'query': 'string', 'tenant_id': 'string'}, 'description': 'Lookup course records for the generated domain.'}, {'name': 'assignment_lookup', 'risk': 'medium', 'review_required': False, 'input_schema': {'query': 'string', 'tenant_id': 'string'}, 'description': 'Lookup assignment records for the generated domain.'}, {'name': 'learning_plan_lookup', 'risk': 'medium', 'review_required': False, 'input_schema': {'query': 'string', 'tenant_id': 'string'}, 'description': 'Lookup learning plan records for the generated domain.'}], 'rag_sources': ['uploaded_documents', 'domain_knowledge_base'], 'human_review_triggers': ['external_send', 'high_risk_recommendation', 'sensitive_data_access'], 'eval_cases': [{'name': 'answer_course_questions_smoke', 'input': 'Run answer_course_questions for a sample Education request.', 'expected': {'safe_response': True}}, {'name': 'grade_with_review_smoke', 'input': 'Run grade_with_review for a sample Education request.', 'expected': {'safe_response': True}}, {'name': 'recommend_learning_plan_smoke', 'input': 'Run recommend_learning_plan for a sample Education request.', 'expected': {'safe_response': True}}]}
router = APIRouter(prefix="/v1/domain", tags=["domain"])


@router.get("/profile")
def get_domain_profile() -> dict[str, Any]:
    return DOMAIN_PROFILE


@router.get("/entities")
def get_domain_entities() -> list[str]:
    return list(ENTITY_MODELS)


@router.post("/{entity_name}")
def create_domain_record(
    entity_name: str,
    data: DomainRecordCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    model = _model_for(entity_name)
    record = model(
        tenant_id=data.tenant_id,
        title=data.title,
        status=data.status,
        summary=data.summary,
        metadata_json=data.metadata_json,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _serialize(record)


@router.get("/{entity_name}")
def list_domain_records(
    entity_name: str,
    tenant_id: str = Query(...),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    model = _model_for(entity_name)
    rows = db.scalars(
        select(model).where(model.tenant_id == tenant_id).order_by(model.created_at.desc())
    ).all()
    return [_serialize(row) for row in rows]


@router.patch("/{entity_name}/{record_id}")
def update_domain_record(
    entity_name: str,
    record_id: str,
    data: DomainRecordUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    model = _model_for(entity_name)
    record = db.get(model, record_id)
    if record is None or record.tenant_id != data.tenant_id:
        raise HTTPException(status_code=404, detail="record not found")
    for field in ("title", "status", "summary", "metadata_json"):
        value = getattr(data, field)
        if value is not None:
            setattr(record, field, value)
    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return _serialize(record)


def _model_for(entity_name: str):
    model = ENTITY_MODELS.get(entity_name)
    if model is None:
        raise HTTPException(status_code=404, detail=f"unknown domain entity: {entity_name}")
    return model


def _serialize(record) -> dict[str, Any]:
    return {
        "id": record.id,
        "tenant_id": record.tenant_id,
        "title": record.title,
        "status": record.status,
        "summary": record.summary,
        "metadata_json": record.metadata_json,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }
