# 04 API 地图

## 核心生成链路

- `POST /v1/builder/runs`
- `POST /v1/builder/runs/{run_id}/invoke`
- `GET /v1/chat/runs/{run_id}`
- `POST /v1/reviews/{review_id}/decide`
- `GET /v1/generated-projects/{project_id}/versions`
- `GET /v1/generated-projects/{project_id}/validations`
- `GET /v1/generated-projects/{project_id}/eval-reports`
- `POST /v1/generated-projects/{project_id}/repair`

## 支撑能力

- 用户租户：`/v1/tenants`、`/v1/users`
- 认证：`/v1/users/{user_id}/api-token`、`/v1/auth/whoami`
- Memory：`/v1/memories`、`/v1/sessions/{session_id}/memory-context`
- RAG：`/v1/knowledge-bases`
- 模型：`/v1/model-providers`、`/v1/model-registry`
- 模板：`/v1/domain-templates`

