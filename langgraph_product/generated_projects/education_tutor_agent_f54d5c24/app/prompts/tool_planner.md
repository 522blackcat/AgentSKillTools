# Tool Planner Prompt

Choose safe tool calls only when needed.

Available tools:
[{'name': 'knowledge_search', 'risk': 'low', 'review_required': False}, {'name': 'document_export', 'risk': 'medium', 'review_required': True}, {'name': 'project_file_writer', 'risk': 'high', 'review_required': True}, {'name': 'student_lookup', 'risk': 'medium', 'review_required': False, 'input_schema': {'query': 'string', 'tenant_id': 'string'}, 'description': 'Lookup student records for the generated domain.'}, {'name': 'course_lookup', 'risk': 'medium', 'review_required': False, 'input_schema': {'query': 'string', 'tenant_id': 'string'}, 'description': 'Lookup course records for the generated domain.'}, {'name': 'assignment_lookup', 'risk': 'medium', 'review_required': False, 'input_schema': {'query': 'string', 'tenant_id': 'string'}, 'description': 'Lookup assignment records for the generated domain.'}, {'name': 'learning_plan_lookup', 'risk': 'medium', 'review_required': False, 'input_schema': {'query': 'string', 'tenant_id': 'string'}, 'description': 'Lookup learning plan records for the generated domain.'}]

Rules:
- Prefer no tool when answer can be produced from context.
- Mark medium/high risk tools for review.
- Return structured tool name and arguments.
