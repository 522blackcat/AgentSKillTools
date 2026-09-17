"""Generated tool contracts and safe stub executor."""

from __future__ import annotations

from typing import Any


TOOL_REGISTRY = [{'name': 'knowledge_search', 'risk': 'low', 'review_required': False}, {'name': 'document_export', 'risk': 'medium', 'review_required': True}, {'name': 'project_file_writer', 'risk': 'high', 'review_required': True}, {'name': 'student_lookup', 'risk': 'medium', 'review_required': False, 'input_schema': {'query': 'string', 'tenant_id': 'string'}, 'description': 'Lookup student records for the generated domain.'}, {'name': 'course_lookup', 'risk': 'medium', 'review_required': False, 'input_schema': {'query': 'string', 'tenant_id': 'string'}, 'description': 'Lookup course records for the generated domain.'}, {'name': 'assignment_lookup', 'risk': 'medium', 'review_required': False, 'input_schema': {'query': 'string', 'tenant_id': 'string'}, 'description': 'Lookup assignment records for the generated domain.'}, {'name': 'learning_plan_lookup', 'risk': 'medium', 'review_required': False, 'input_schema': {'query': 'string', 'tenant_id': 'string'}, 'description': 'Lookup learning plan records for the generated domain.'}]


def list_tools() -> list[dict[str, Any]]:
    return TOOL_REGISTRY


def execute_tool(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    tool = next((item for item in TOOL_REGISTRY if item["name"] == tool_name), None)
    if tool is None:
        raise ValueError(f"unknown tool: {tool_name}")
    return {
        "tool_name": tool_name,
        "status": "stubbed",
        "risk": tool.get("risk", "medium"),
        "review_required": tool.get("review_required", True),
        "input_echo": payload,
        "message": "Replace this stub with a real connector or domain service.",
    }
