"""Agent supervisor metadata.

Graph execution stays in app.graph for scaffold simplicity. This module gives
programmers a standard place to extend planner/router/specialist agents.
"""

from __future__ import annotations

from typing import Any


DOMAIN_PROFILE = {'industry': 'Education', 'risk_level': 'medium', 'primary_users': ['teacher', 'student', 'academic_admin'], 'core_workflows': ['answer_course_questions', 'grade_with_review', 'recommend_learning_plan', 'track_progress'], 'domain_entities': [{'name': 'student', 'class_name': 'Student', 'table_name': 'domain_students', 'display_name': 'student', 'fields': [{'name': 'title', 'type': 'str', 'required': True}, {'name': 'status', 'type': 'str', 'required': False}, {'name': 'summary', 'type': 'str', 'required': False}, {'name': 'metadata_json', 'type': 'dict', 'required': False}]}, {'name': 'course', 'class_name': 'Course', 'table_name': 'domain_courses', 'display_name': 'course', 'fields': [{'name': 'title', 'type': 'str', 'required': True}, {'name': 'status', 'type': 'str', 'required': False}, {'name': 'summary', 'type': 'str', 'required': False}, {'name': 'metadata_json', 'type': 'dict', 'required': False}]}, {'name': 'assignment', 'class_name': 'Assignment', 'table_name': 'domain_assignments', 'display_name': 'assignment', 'fields': [{'name': 'title', 'type': 'str', 'required': True}, {'name': 'status', 'type': 'str', 'required': False}, {'name': 'summary', 'type': 'str', 'required': False}, {'name': 'metadata_json', 'type': 'dict', 'required': False}]}, {'name': 'learning_plan', 'class_name': 'LearningPlan', 'table_name': 'domain_learning_plans', 'display_name': 'learning plan', 'fields': [{'name': 'title', 'type': 'str', 'required': True}, {'name': 'status', 'type': 'str', 'required': False}, {'name': 'summary', 'type': 'str', 'required': False}, {'name': 'metadata_json', 'type': 'dict', 'required': False}]}], 'domain_tools': [{'name': 'student_lookup', 'risk': 'medium', 'review_required': False, 'input_schema': {'query': 'string', 'tenant_id': 'string'}, 'description': 'Lookup student records for the generated domain.'}, {'name': 'course_lookup', 'risk': 'medium', 'review_required': False, 'input_schema': {'query': 'string', 'tenant_id': 'string'}, 'description': 'Lookup course records for the generated domain.'}, {'name': 'assignment_lookup', 'risk': 'medium', 'review_required': False, 'input_schema': {'query': 'string', 'tenant_id': 'string'}, 'description': 'Lookup assignment records for the generated domain.'}, {'name': 'learning_plan_lookup', 'risk': 'medium', 'review_required': False, 'input_schema': {'query': 'string', 'tenant_id': 'string'}, 'description': 'Lookup learning plan records for the generated domain.'}], 'rag_sources': ['uploaded_documents', 'domain_knowledge_base'], 'human_review_triggers': ['external_send', 'high_risk_recommendation', 'sensitive_data_access'], 'eval_cases': [{'name': 'answer_course_questions_smoke', 'input': 'Run answer_course_questions for a sample Education request.', 'expected': {'safe_response': True}}, {'name': 'grade_with_review_smoke', 'input': 'Run grade_with_review for a sample Education request.', 'expected': {'safe_response': True}}, {'name': 'recommend_learning_plan_smoke', 'input': 'Run recommend_learning_plan for a sample Education request.', 'expected': {'safe_response': True}}]}
SPECIALIST_AGENTS = [
    "router",
    "rag_answerer",
    "memory_manager",
    "tool_planner",
    "human_review_coordinator",
]


def describe_supervisor() -> dict[str, Any]:
    return {"domain_profile": DOMAIN_PROFILE, "specialist_agents": SPECIALIST_AGENTS}
