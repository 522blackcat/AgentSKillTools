# langgraph_product 独立生产级 AI Agent 平台设计文档

## 1. 定位

`langgraph_product` 是一个独立生产项目，不依赖其它学习目录。

目标不是做一个演示 Agent，而是做一个“生产级 Agent Builder + Runtime”：用户输入“生成一个律所 AI Agent”或“生成一个医院 AI Agent”时，系统能生成一套可运行、可测试、可扩展、带数据库、RAG、工具、记忆、人工审核、多 Agent 协作和运行观测的 Agent 项目。

核心原则：

- 生产优先，不兼容学习路径。
- 数据先行，所有运行、记忆、审核、工具调用可落库和回放。
- 高风险领域默认人工审核。
- 多 Agent 用于受控分工，不做失控自治。
- 生成代码必须可运行、可测试、可审计。
- 法律、医疗等高风险领域生成工程基础设施，不生成免审上线的专业服务。

## 2. 推荐技术栈

后端：

- Python 3.12
- FastAPI
- Uvicorn
- LangGraph
- LangChain Core
- Pydantic v2
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- pgvector
- Redis
- RQ
- structlog
- OpenTelemetry
- ruff
- mypy
- pytest
- tenacity
- tiktoken 或兼容 tokenizer

Agent 能力：

- LangGraph StateGraph
- LangGraph checkpoint
- LangGraph interrupt / resume
- Structured output
- Tool calling
- Multi-agent supervisor graph
- RAG with hybrid retrieval
- Long-term memory
- Model gateway
- Artifact versioning
- Sandbox validation

存储：

- PostgreSQL：用户、会话、记忆、运行记录、审核记录、文档元数据。
- pgvector：文档 chunk embedding、记忆 embedding。
- Redis：短期缓存、任务队列、任务状态、限流。
- 本地文件或对象存储：生成项目文件、上传文档、导出包。

第一版本地开发可用 Docker Compose 启动 PostgreSQL、pgvector、Redis。不要用 JSON 文件当生产存储。

技术取舍：

- 后台任务第一版使用 RQ，不使用 Celery。RQ 部署简单，足够支撑文档导入、embedding、项目生成和测试运行。
- pgvector 先承担向量检索。规模扩大后再拆到专用向量库。
- 文件存储第一版使用本地 workspace storage，接口按对象存储抽象，后续可换 S3 / MinIO。
- Auth 第一版使用 API token + 本地用户表，接口保留 OAuth / SSO 扩展点。
- UI 不作为第一版重点，先提供 API 和 CLI。
- 模型调用必须走 Model Gateway，不允许节点直接调用 provider SDK。

## 3. 核心能力

平台必须支持：

- 用户管理和租户隔离。
- 会话管理。
- 长期记忆数据库。
- RAG 知识库。
- 工具注册和工具执行。
- LangGraph 人工审核。
- 多 Agent 协作。
- 垂直领域 Agent 代码生成。
- 自动测试和项目校验。
- 运行 trace 和审计日志。
- 权限、限流、错误处理。
- Token 用量追踪、额度分配、预算控制。
- 模型网关、fallback、retry、timeout。
- 幂等写接口和幂等任务。
- 生成项目版本管理。
- 沙箱化测试运行。
- 密钥管理和隐私治理。
- 事件流和运行进度订阅。
- 备份、恢复、健康检查。

第一版必须跑通的端到端场景：

1. 创建用户和租户。
2. 创建会话。
3. 导入知识文档并生成 embedding。
4. 用户提问，Agent 通过 RAG 带引用回答。
5. 用户要求生成律所或医院 Agent 项目。
6. 多 Agent 产出 blueprint。
7. 高风险写文件动作进入人工审核。
8. 审核通过后写入生成项目。
9. 自动运行测试并保存结果。
10. 每次 LLM / embedding 调用都有 token 记录和额度扣减。
11. 生成项目产生版本快照，可查看 diff 和回滚。
12. 生成项目测试在沙箱中运行。
13. 全流程 run、event、tool call、review、validation 可回放。

## 4. 总体架构

```text
Client / CLI / API
  |
  v
FastAPI Gateway
  |
  +-- Auth / Tenant Context
  +-- Rate Limit
  +-- Request Validation
  +-- Idempotency
  |
  v
Agent Runtime
  |
  +-- LangGraph Main Graph
  +-- PostgreSQL Checkpointer
  +-- Human Review Interrupt
  +-- Multi-Agent Supervisor
  +-- Model Gateway
  |
  v
Service Layer
  |
  +-- User Service
  +-- Memory Service
  +-- Knowledge Service
  +-- Tool Service
  +-- Project Generator Service
  +-- Review Service
  +-- Observability Service
  +-- Billing / Quota Service
  +-- Artifact Version Service
  +-- Sandbox Service
  +-- Domain Template Service
  |
  v
Data Layer
  |
  +-- PostgreSQL + pgvector
  +-- Redis
  +-- File / Object Storage
```

运行边界：

- API 进程只处理短请求。
- 文档导入、embedding、项目生成、测试运行放入 RQ worker。
- LangGraph checkpoint 保存可恢复状态。
- 人工审核以 checkpoint thread 作为恢复入口。
- 生成项目只写入受控 workspace，不允许任意路径写入。
- 模型调用统一经过 Model Gateway。
- 测试、lint、生成代码执行必须进入 Sandbox Service。

## 5. 主图流程

```text
load_user_context
  |
  v
input_guard
  |
  v
load_memory
  |
  v
intent_router
  |
  +-- direct_answer
  |
  +-- retrieve_knowledge -> answer_with_evidence
  |
  +-- plan_tools -> risk_check -> execute_tools -> answer_with_tools
  |
  +-- agent_builder_supervisor -> project_review -> write_project -> validate_project
  |
  +-- clarify
  |
  +-- reject
  |
  v
update_memory
  |
  v
persist_run
```

长任务流程：

```text
API request
  |
  v
create agent_run
  |
  v
enqueue RQ job
  |
  v
worker invokes graph
  |
  +-- complete -> persist result
  |
  +-- interrupt -> persist review_request
  |
  +-- fail -> persist error
```

## 6. Agent State

```python
class AgentState(TypedDict, total=False):
    tenant_id: str
    user_id: str
    session_id: str
    run_id: str

    user_input: str
    normalized_input: str
    messages: list[dict]

    intent: str
    route: str
    risk_level: str
    token_budget: dict
    token_usage: dict

    memory_context: str
    memory_candidates: list[dict]

    rag_query: str
    rag_results: list[dict]
    rag_context: str

    tool_plan: list[dict]
    tool_results: list[dict]

    review_required: bool
    review_request: dict
    review_decision: dict

    builder_request: dict
    agent_blueprint: dict
    agent_artifacts: list[dict]
    generated_files: list[dict]
    validation_results: list[dict]

    final_answer: str
    errors: list[dict]
    trace: list[dict]
```

状态规则：

- `tenant_id`、`user_id` 只来自认证层。
- LLM 不能生成或修改身份字段。
- 节点只更新自己负责的字段。
- 每个节点必须写 trace event。
- 高风险动作必须设置 `review_required=true`。
- `trace` 只放摘要，完整 payload 写数据库。
- `messages` 只保留当前窗口，长期历史从数据库加载。
- `generated_files` 只保存路径、hash、角色，不在 state 中保存大文件内容。
- `token_budget` 在 run 开始时冻结，节点只能消费，不能自行扩额。
- `token_usage` 每个模型调用后更新，并落库。

## 7. API 设计

第一版 API：

```text
POST /v1/tenants
POST /v1/users
POST /v1/sessions

POST /v1/chat/runs
GET  /v1/chat/runs/{run_id}
GET  /v1/chat/runs/{run_id}/events

POST /v1/knowledge-bases
POST /v1/knowledge-bases/{kb_id}/documents
GET  /v1/knowledge-bases/{kb_id}/documents/{document_id}

POST /v1/builder/runs
GET  /v1/builder/runs/{run_id}
GET  /v1/generated-projects/{project_id}
GET  /v1/generated-projects/{project_id}/files

GET  /v1/reviews/pending
POST /v1/reviews/{review_id}/decide

GET  /v1/memories
PATCH /v1/memories/{memory_id}
DELETE /v1/memories/{memory_id}

GET  /v1/quotas
POST /v1/quotas/grants
GET  /v1/token-usage
GET  /v1/token-usage/runs/{run_id}

GET  /v1/chat/runs/{run_id}/stream
GET  /v1/builder/runs/{run_id}/stream

GET  /v1/generated-projects/{project_id}/versions
GET  /v1/generated-projects/{project_id}/versions/{version_id}
POST /v1/generated-projects/{project_id}/versions/{version_id}/rollback

GET  /v1/domain-templates
POST /v1/domain-templates
GET  /v1/domain-templates/pending
POST /v1/domain-templates/{template_id}/review
PATCH /v1/domain-templates/{template_id}/status
GET  /v1/domain-templates/{template_id}/improvement-suggestions

POST /v1/feedback

GET  /healthz
GET  /readyz
```

API 规则：

- 所有写接口必须带 `tenant_id` 上下文。
- 所有长任务返回 `run_id`，客户端轮询或订阅事件。
- 审核接口只能由 `reviewer`、`admin`、`owner` 调用。
- 高风险领域模板审批接口只能由 `admin`、`owner` 调用。
- 文件内容下载接口必须做路径校验和权限校验。

Auth 第一版实现：

- `users.api_token_hash` 保存 token hash，不保存明文 token。
- `POST /v1/users/{user_id}/api-token` 为用户签发一次性可见 API token。
- 签发接口必须带 `X-Admin-Secret`，值匹配 `APP_SECRET_KEY`。
- 非 local 环境禁止使用默认 `APP_SECRET_KEY=local-dev`。
- token 格式为 Bearer token，前缀 `agt_`。
- `GET /v1/auth/whoami` 通过 `Authorization: Bearer <token>` 验证当前用户。
- hash 使用 `APP_SECRET_KEY` 作为 HMAC secret。
- Phase 10 将关键写接口切换到强制 Bearer token + RBAC：
  - `POST /v1/secure/quotas/grants` 仅 `admin` / `owner`。
  - `POST /v1/model-providers`、`POST /v1/model-registry` 仅 `admin` / `owner`。
  - `POST /v1/reviews/{review_id}/decide` 要求 reviewer 本人 token，角色为 `reviewer` / `admin` / `owner`。
  - `POST /v1/domain-templates/{template_id}/review` 要求 reviewer 本人 token，角色为 `admin` / `owner`。
  - `PATCH /v1/domain-templates/{template_id}/status` 仅 `admin` / `owner`。
  - generated project `rollback` / `repair` 仅 `admin` / `owner`。
- 旧 `POST /v1/quotas/grants` 返回 `410`，要求使用受保护的 `/v1/secure/quotas/grants`。
- 后续继续把普通业务写接口切换到认证上下文，逐步移除 body 中的可伪造 `user_id`。
- 普通用户只能查看自己的 token 用量。
- `admin`、`owner` 可以给用户或租户发放 token grant。
- 写接口必须支持 `Idempotency-Key`。
- stream 接口使用 SSE。

## 8. Model Gateway

所有模型调用必须通过 Model Gateway。图节点、工具、子 Agent 不直接调用 provider SDK。

职责：

- 统一 chat、embedding、rerank、structured output 调用。
- 根据任务类型选择模型。
- 处理 retry、timeout、fallback、circuit breaker。
- 归一化 token usage。
- 写入 `token_usage_events`。
- 应用 prompt cache / response cache。
- 执行预算检查。

模型角色：

```text
cheap_chat: 低成本路由、摘要、简单回答
strong_chat: 复杂推理、builder、代码生成
structured_output: 强 JSON schema 输出
embedding: 文档和记忆向量
rerank: RAG 结果重排
safety: 高风险分类和拒答判定
```

模型注册：

```text
model_providers
  id uuid primary key
  name text
  provider_type text
  base_url text
  status text
  created_at timestamptz

model_registry
  id uuid primary key
  provider_id uuid
  model_id text
  role text
  context_window integer
  input_cost_per_1k numeric
  output_cost_per_1k numeric
  supports_json_schema boolean
  supports_tools boolean
  status text
  created_at timestamptz
```

调用策略：

- Router 默认用 `cheap_chat`。
- Builder 和代码生成默认用 `strong_chat`。
- 所有结构化输出优先用支持 JSON schema 的模型。
- 主模型失败时按 role fallback。
- provider 连续失败进入 circuit open，短时间不再调用。
- timeout、retry、fallback 都必须写 trace。

## 9. 幂等设计

生产系统必须允许客户端重试、worker 重试、网络失败后恢复。

```text
idempotency_keys
  id uuid primary key
  tenant_id uuid
  user_id uuid
  key text
  request_hash text
  response_json jsonb
  status text
  expires_at timestamptz
  created_at timestamptz
  updated_at timestamptz
```

必须幂等的动作：

- 创建 run。
- 创建 review decision。
- token 扣减。
- 写 generated file。
- 创建 project version。
- 执行 RQ job。

规则：

- 同一 `Idempotency-Key` + 同一 request hash 返回同一结果。
- 同一 key 但 request hash 不同，返回冲突错误。
- review decision 只能成功一次。
- token 扣减必须带 `usage_event_id`，重复事件不重复扣。
- 文件写入先写临时文件，再原子 rename。

## 10. 用户管理

最小用户体系：

```text
tenants
  id uuid primary key
  name text
  plan text
  status text
  created_at timestamptz
  updated_at timestamptz

users
  id uuid primary key
  tenant_id uuid references tenants(id)
  email text
  username text
  display_name text
  role text
  status text
  created_at timestamptz
  updated_at timestamptz

user_profiles
  user_id uuid primary key references users(id)
  locale text
  timezone text
  preferences jsonb
  safety_profile jsonb
  updated_at timestamptz
```

权限角色：

- `owner`: 管理租户、用户、知识库、工具。
- `admin`: 管理知识库、工具、审核。
- `reviewer`: 处理人工审核。
- `developer`: 生成和修改 Agent 项目。
- `user`: 使用 Agent。

数据隔离：

- 所有业务表必须带 `tenant_id`。
- 查询层默认注入 `tenant_id` 条件。
- 审计日志记录 `user_id`、`tenant_id`、`run_id`。

## 11. Token 追踪与额度机制

生产级 Agent 必须把 token 当作可审计资源。原因：

- 控制成本。
- 防止多 Agent builder 无限消耗。
- 支持用户额度、租户额度、项目额度。
- 支持问题排查：哪次 run、哪个节点、哪个模型消耗最多。

### 11.1 Token 表

```text
token_quota_accounts
  id uuid primary key
  tenant_id uuid
  user_id uuid null
  scope text
  status text
  created_at timestamptz
  updated_at timestamptz

token_quotas
  id uuid primary key
  tenant_id uuid
  account_id uuid
  quota_type text
  token_limit bigint
  token_used bigint
  reset_at timestamptz
  created_at timestamptz
  updated_at timestamptz

token_grants
  id uuid primary key
  tenant_id uuid
  account_id uuid
  granted_tokens bigint
  remaining_tokens bigint
  reason text
  granted_by_user_id uuid
  expires_at timestamptz
  created_at timestamptz

token_usage_events
  id uuid primary key
  tenant_id uuid
  user_id uuid
  run_id uuid
  node_name text
  call_type text
  model_provider text
  model_id text
  prompt_tokens integer
  completion_tokens integer
  embedding_tokens integer
  rerank_tokens integer
  total_tokens integer
  estimated_cost numeric
  metadata jsonb
  created_at timestamptz
```

字段说明：

- `scope`: `tenant`、`user`、`project`。
- `quota_type`: `daily`、`monthly`、`run`、`project`、`grant`。
- `call_type`: `chat_completion`、`embedding`、`rerank`、`structured_output`。
- `token_limit`: 周期额度。
- `token_used`: 周期内已用量。
- `granted_tokens`: 管理员额外发放额度。
- `remaining_tokens`: grant 剩余额度。

### 11.2 额度来源

额度来源按优先级扣减：

1. 即将过期的 `token_grants`。
2. 用户级周期额度。
3. 租户级周期额度。
4. 项目专属额度。

规则：

- run 开始前预估预算并检查额度。
- 节点执行前检查剩余预算。
- 模型调用后按真实 token 用量扣减。
- 如果 provider 没返回 token usage，用本地 tokenizer 估算并标记 `estimated=true`。
- token 扣减必须在数据库事务中完成。

### 11.3 Run 预算

不同 route 默认预算：

```text
direct: 4k tokens
rag: 12k tokens
tool: 16k tokens
builder blueprint: 80k tokens
builder full project: 300k tokens
eval run: 120k tokens
```

预算策略：

- Router 先给出 `route` 和 `risk_level`。
- Budget Service 根据 route 分配 `token_budget`。
- Supervisor 给每个子 Agent 分配子预算。
- 子 Agent 超预算必须停止并返回 partial artifact。
- 用户可显式设置更低预算。
- 超过高预算阈值需要人工确认或管理员权限。

### 11.4 超额策略

超额时按场景降级：

- chat direct：拒绝新请求，提示额度不足。
- RAG：减少 `top_k`、关闭 rerank，再不足则拒绝。
- builder：停止新子 Agent，保存 partial blueprint。
- eval：停止剩余 case，保存已完成结果。
- tool：不执行高成本工具。

最终回答必须说明：

- 当前额度不足。
- 已保存哪些中间结果。
- 需要多少额外 token 继续。

### 11.5 多 Agent token 控制

Supervisor 必须维护预算账本：

```python
class TokenBudget(TypedDict):
    total_limit: int
    used: int
    remaining: int
    per_agent_limit: dict[str, int]
    hard_stop: bool
```

规则：

- 每个 Specialist 有最大 token。
- Specialist 不能向模型请求无限上下文。
- Code Generator 分文件生成，每个文件有 token 上限。
- Test Agent 失败重试次数有限。
- Supervisor 不能把未用完的安全预算转给高风险 Agent，除非人审通过。

### 11.6 Token API

```text
GET /v1/quotas
  返回当前用户和租户额度。

POST /v1/quotas/grants
  管理员发放 token。

GET /v1/token-usage
  查询时间范围内 token 用量。

GET /v1/token-usage/runs/{run_id}
  查询单次 run 的节点级 token 用量。

GET /v1/model-providers
POST /v1/model-providers
  管理模型供应商。local 默认使用 `stub`，生产可配置 OpenAI-compatible provider。

GET /v1/model-registry
POST /v1/model-registry
  管理 role 到具体模型的映射，例如 `cheap_chat`、`builder`、`embedding`。
```

### 11.7 Token 验收标准

- 每次 LLM 调用都有 `token_usage_events`。
- 每次 embedding 调用都有 `token_usage_events`。
- run 开始前检查额度。
- 模型调用后扣减额度。
- 多 Agent builder 不会超过 run budget。
- 超额时保存 partial result。
- 管理员可以给用户发放 token grant。
- 模型调用记录 provider、model_id、prompt/completion/embedding/rerank token。
- 本地默认 provider 不需要外网；生产 provider 保留 base_url、成本、能力标记和状态字段。

## 12. 数据库设计

### 12.1 会话和消息

```text
chat_sessions
  id uuid primary key
  tenant_id uuid
  user_id uuid
  title text
  summary text
  status text
  created_at timestamptz
  updated_at timestamptz

chat_messages
  id uuid primary key
  tenant_id uuid
  session_id uuid
  role text
  content text
  metadata jsonb
  token_count integer
  created_at timestamptz
```

### 12.2 长期记忆

```text
user_memories
  id uuid primary key
  tenant_id uuid
  user_id uuid
  category text
  memory_key text
  memory_value text
  confidence numeric
  source_session_id uuid
  source_message_id uuid
  embedding vector
  is_active boolean
  created_at timestamptz
  updated_at timestamptz
```

记忆分类：

- `preference`: 输出语言、格式、技术栈。
- `profile`: 稳定用户背景。
- `project_fact`: 项目事实。
- `decision`: 明确决策。
- `constraint`: 长期约束。

写入规则：

- 只保存稳定事实，不保存临时对话。
- 置信度低于 `0.75` 不入库。
- 敏感信息默认不入库。
- 用户可查看、修正、禁用、删除长期记忆。

### 12.2.1 三层 Memory 运行模型

生产级 Memory 必须同时包含短期记忆、摘要记忆和长期记忆。

短期记忆：

- 表：`chat_messages`。
- 内容：当前会话最近 N 条 user/assistant 消息。
- 加载点：graph `load_memory` 前由 runtime 查询最近消息并注入 `messages`。
- 写入点：graph 完成后由 runtime 写入本轮 user message 和 assistant message。
- 用途：保持当前对话连续性。

摘要记忆：

- 表：`chat_sessions.summary`。
- 内容：当前会话较早消息的压缩摘要。
- 触发：消息数量超过阈值后更新 summary。
- 加载点：runtime 与短期记忆一起加载。
- 用途：避免 prompt 过长，同时保留会话主线。

长期记忆：

- 表：`user_memories`。
- 内容：跨会话稳定事实、偏好、项目决策、长期约束。
- 检索：用当前 query 对 `user_memories.embedding` 做向量/关键词混合召回。
- 加载点：runtime 注入 `memory_candidates` 和 `memory_context`。
- 写入点：第一版通过 API 写入；后续由 memory extraction 节点自动抽取候选，必要时进入人工审核。

Memory 上下文结构：

```text
memory_context
  ├─ 会话摘要 chat_sessions.summary
  ├─ 最近对话 chat_messages[-N:]
  └─ 长期记忆 user_memories top_k
```

验收标准：

- 每轮 run 后 `chat_messages` 增加 user/assistant 两条消息。
- 长会话触发 `chat_sessions.summary` 更新。
- `load_memory` trace 能看到 recent message 数量、长期记忆数量和 summary 是否存在。
- 用户长期记忆能通过 `/v1/memories/search` 召回。
- `/v1/sessions/{session_id}/memory-context` 能展示三层 memory context。

### 12.3 知识库和 RAG

```text
knowledge_bases
  id uuid primary key
  tenant_id uuid
  name text
  domain text
  description text
  created_at timestamptz

documents
  id uuid primary key
  tenant_id uuid
  knowledge_base_id uuid
  title text
  source_uri text
  doc_type text
  checksum text
  status text
  metadata jsonb
  created_at timestamptz

document_chunks
  id uuid primary key
  tenant_id uuid
  document_id uuid
  chunk_id text
  parent_chunk_id text
  chunk_type text
  section_title text
  location text
  text text
  embedding vector
  metadata jsonb
  created_at timestamptz
```

RAG 策略：

- 短文本：完整语义 chunk。
- 中文本：标题和段落 chunk。
- 长文本：章节摘要路由 + leaf chunk 精检。
- 检索：BM25 + vector hybrid retrieval。
- 重排：cross-encoder 或 LLM rerank。
- 输出：必须带 source、section、location、score。

### 12.4 LangGraph checkpoint

checkpoint 必须落 PostgreSQL，支撑中断、恢复和失败回放。

```text
graph_threads
  id uuid primary key
  tenant_id uuid
  user_id uuid
  thread_key text
  graph_name text
  status text
  created_at timestamptz
  updated_at timestamptz

graph_checkpoints
  id uuid primary key
  tenant_id uuid
  thread_id uuid
  checkpoint_id text
  parent_checkpoint_id text
  state jsonb
  metadata jsonb
  created_at timestamptz
```

规则：

- `thread_key` 与 `session_id` 或 `run_id` 绑定。
- 人工审核恢复必须使用同一个 `thread_key`。
- checkpoint 存业务状态，不存模型隐藏推理。
- 大文件内容不进 checkpoint。

### 12.5 运行记录

```text
agent_runs
  id uuid primary key
  tenant_id uuid
  user_id uuid
  session_id uuid
  graph_name text
  input jsonb
  output jsonb
  status text
  started_at timestamptz
  finished_at timestamptz

agent_events
  id uuid primary key
  tenant_id uuid
  run_id uuid
  node_name text
  event_type text
  payload jsonb
  latency_ms integer
  ok boolean
  error jsonb
  created_at timestamptz

tool_calls
  id uuid primary key
  tenant_id uuid
  run_id uuid
  tool_name text
  arguments jsonb
  result jsonb
  risk_level text
  status text
  latency_ms integer
  created_at timestamptz

retrieval_logs
  id uuid primary key
  tenant_id uuid
  run_id uuid
  query text
  rewritten_query text
  top_k integer
  results jsonb
  created_at timestamptz
```

### 12.6 人工审核

```text
human_review_requests
  id uuid primary key
  tenant_id uuid
  run_id uuid
  requester_user_id uuid
  risk_level text
  reason text
  proposed_action jsonb
  evidence jsonb
  status text
  created_at timestamptz
  decided_at timestamptz

human_review_decisions
  id uuid primary key
  tenant_id uuid
  review_request_id uuid
  reviewer_user_id uuid
  decision text
  comment text
  revised_action jsonb
  created_at timestamptz
```

### 12.7 生成项目

```text
generated_projects
  id uuid primary key
  tenant_id uuid
  owner_user_id uuid
  name text
  domain text
  status text
  blueprint jsonb
  storage_path text
  created_at timestamptz
  updated_at timestamptz

generated_files
  id uuid primary key
  tenant_id uuid
  project_id uuid
  path text
  content_hash text
  file_role text
  created_at timestamptz

project_validations
  id uuid primary key
  tenant_id uuid
  project_id uuid
  version_id uuid
  command text
  status text
  output text
  created_at timestamptz
```

### 12.8 Artifact 版本

```text
project_versions
  id uuid primary key
  tenant_id uuid
  project_id uuid
  version_number integer
  blueprint jsonb
  manifest jsonb
  diff_summary text
  status text
  created_by_run_id uuid
  created_at timestamptz

file_versions
  id uuid primary key
  tenant_id uuid
  project_id uuid
  version_id uuid
  path text
  content_hash text
  storage_uri text
  change_type text
  created_at timestamptz
```

规则：

- 每次生成或修改项目都创建新 `project_versions`。
- 回滚只切换 active version，不直接覆盖历史文件。
- validation 绑定 version。
- final report 必须说明新增、修改、删除文件。

### 12.9 密钥和外部连接

```text
secrets
  id uuid primary key
  tenant_id uuid
  name text
  encrypted_value bytea
  provider text
  key_version text
  created_by_user_id uuid
  created_at timestamptz
  rotated_at timestamptz

external_connections
  id uuid primary key
  tenant_id uuid
  name text
  connection_type text
  secret_id uuid
  scopes jsonb
  status text
  created_at timestamptz
```

规则：

- secret 不进入 prompt、trace、checkpoint、generated files。
- generated project 只写 `.env.example`。
- secret 支持 rotation。
- 日志必须脱敏。

### 12.10 Domain Template Registry

```text
domain_templates
  id uuid primary key
  tenant_id uuid null
  domain text
  name text
  version text
  compliance_profile jsonb
  required_modules jsonb
  default_prompts jsonb
  required_eval_cases jsonb
  status text
  created_at timestamptz
```

用途：

- 注册律所、医院、金融、教育等领域模板。
- 定义必需模块和审核规则。
- 定义默认 prompt 和 eval cases。
- 支持模板版本升级。

### 12.11 反馈和质量闭环

```text
feedback_items
  id uuid primary key
  tenant_id uuid
  user_id uuid
  run_id uuid
  rating integer
  category text
  comment text
  correction jsonb
  created_at timestamptz

quality_issues
  id uuid primary key
  tenant_id uuid
  source_feedback_id uuid
  issue_type text
  severity text
  status text
  owner_user_id uuid
  created_at timestamptz
```

反馈用途：

- 标记坏答案。
- 收集人工修正。
- 沉淀 eval case。
- 对比 prompt/template/model 版本效果。

### 12.12 备份与恢复

```text
backup_jobs
  id uuid primary key
  tenant_id uuid null
  backup_type text
  target_uri text
  status text
  started_at timestamptz
  finished_at timestamptz
  metadata jsonb
```

要求：

- PostgreSQL 定期备份。
- generated project storage 定期备份。
- 支持 point-in-time recovery。
- 每月做 restore drill。
- 数据删除和导出要可审计。

### 12.13 Worker 和健康状态

```text
worker_heartbeats
  id uuid primary key
  worker_name text
  queue_name text
  status text
  last_seen_at timestamptz
  metadata jsonb

system_health_checks
  id uuid primary key
  component text
  status text
  latency_ms integer
  error text
  checked_at timestamptz
```

建议索引：

- 所有表建 `tenant_id` 索引。
- `chat_messages(session_id, created_at)`。
- `user_memories(user_id, is_active)`。
- `document_chunks using ivfflat/hnsw (embedding)`。
- `agent_events(run_id, created_at)`。
- `human_review_requests(status, created_at)`。

## 13. 人工审核设计

LangGraph 使用 interrupt / resume。

需要人工审核：

- 法律、医疗、财务高风险建议。
- 发邮件、写数据库、删除文件、提交代码。
- 访问敏感数据。
- 写入大量生成文件。
- 生成面向真实终端用户的专业意见。

审核流程：

```text
risk_check
  |
  +-- low -> continue
  |
  +-- medium/high -> interrupt_for_review
                       |
                       v
                    human decision
                       |
       +---------------+---------------+
       |               |               |
       v               v               v
    approve         revise          reject
       |               |               |
       v               v               v
    execute       execute revised   answer_rejected
```

审核决策：

- `approve`: 继续执行。
- `revise`: 使用人工修改后的 action。
- `reject`: 停止动作，给用户解释。
- `needs_more_info`: 回到澄清节点。

审核请求必须展示：

- 用户原始请求。
- Agent 拟执行动作。
- 风险等级。
- 证据来源。
- 将写入或调用的目标。
- 可选决策：approve、revise、reject、needs_more_info。

恢复规则：

- 审核通过后只恢复对应 `run_id`。
- 审核动作必须幂等。
- 同一 review 只能决策一次。
- revise 后必须重新跑 risk_check。

第一版实现：

- graph 输出 `review_required=true` 时，runtime 不直接完成 run。
- runtime 写入 `human_review_requests`，run 状态变为 `awaiting_review`。
- 同时写入 `GraphCheckpoint(run_id:awaiting_review)`，保留可恢复 state。
- `/v1/reviews/pending` 返回待审核列表。
- `/v1/reviews/{review_id}/decide` 支持 `approve` 和 `reject`。
- 只有 `reviewer`、`admin`、`owner` 角色可提交审核决策。
- 审核决策写入 `human_review_decisions`，并写 `review.decided` event。
- 第一版 approve 将 run 标记为 `completed`，写入 `run.completed.after_review` event。
- 如果 run 绑定 session，approve 后写入本轮 user/assistant 到 `chat_messages`，保证审核恢复后会话连续。
- 第一版 reject 将 run 标记为 `rejected`，并覆盖最终回答。
- reject 写入 `run.rejected.after_review` event，不写会话消息。
- revise / needs_more_info 保留在设计中，等 tool execution 和 builder codegen 节点完成后接入。

## 14. 多 Agent 设计

采用 Supervisor + Specialist 子图。

```text
Supervisor
  |
  +-- Requirements Agent
  +-- Domain Expert Agent
  +-- Product Architect Agent
  +-- Data Architect Agent
  +-- RAG Engineer Agent
  +-- Tooling Agent
  +-- Compliance Agent
  +-- Security Agent
  +-- Code Generator Agent
  +-- Test Engineer Agent
  +-- Documentation Agent
```

Supervisor 负责：

- 拆分任务。
- 选择子 Agent。
- 合并产物。
- 发现冲突。
- 触发人工审核。
- 决定是否进入代码生成。

子 Agent 规则：

- 每个 Agent 输出结构化 artifact。
- 子 Agent 不直接写文件。
- 子 Agent 不执行高风险工具。
- 所有冲突交给 Supervisor。

统一协议：

```python
class AgentTask(TypedDict):
    task_id: str
    domain: str
    objective: str
    constraints: list[str]
    context: dict
    output_schema: dict

class AgentArtifact(TypedDict):
    task_id: str
    agent_name: str
    status: str
    artifact_type: str
    content: dict
    risks: list[dict]
    questions: list[str]
```

冲突处理：

- `Compliance Agent` 可否决 `Code Generator Agent` 的不安全方案。
- `Security Agent` 可要求加入权限、人审、审计。
- `Data Architect Agent` 与 `RAG Engineer Agent` 冲突时，由 Supervisor 统一 schema。
- 冲突无法自动解决时进入 clarify 或 human_review。

## 15. Agent Builder

用户输入：

```text
生成一个生产级律所 AI Agent
```

系统输出：

- 需求分析。
- 领域边界。
- 数据库 schema。
- LangGraph 图。
- 多 Agent 角色。
- RAG 知识库设计。
- 工具设计。
- 人工审核点。
- 合规和安全策略。
- 完整代码。
- 测试。
- README 和运行手册。

生成流程：

```text
parse_builder_request
  |
  v
requirements_agent
  |
  v
domain_expert_agent
  |
  v
architecture_agent
  |
  v
data_architect_agent
  |
  v
rag_engineer_agent
  |
  v
tooling_agent
  |
  v
compliance_agent
  |
  v
security_agent
  |
  v
supervisor_merge
  |
  v
human_review
  |
  v
code_generator_agent
  |
  v
test_engineer_agent
  |
  v
validate_project
  |
  v
final_report
```

Blueprint schema：

```python
class AgentBlueprint(BaseModel):
    name: str
    domain: str
    users: list[str]
    use_cases: list[str]
    risk_profile: dict
    graph: dict
    agents: list[dict]
    database: dict
    rag: dict
    tools: list[dict]
    memory: dict
    human_review: dict
    security: dict
    tests: list[dict]
```

第一版实现：

- `app/builder/service.py` 提供确定性 multi-agent builder。
- 每个 specialist agent 返回结构化 section，后续可逐个替换为真实 LLM 调用。
- 当前 specialist agents：
  - `Requirements Agent`
  - `Architecture Agent`
  - `Data Architect Agent`
  - `RAG Engineer Agent`
  - `Memory Engineer Agent`
  - `Tooling Agent`
  - `Human Review Agent`
  - `Security Agent`
  - `Test Engineer Agent`
  - `Code Generator Agent`
- Supervisor 合并为统一 `agent_blueprint`。
- `validation` 检查必需 specialist 是否齐全。
- `readiness.status=ready_for_project_generation` 表示可进入代码生成阶段。
- law_firm / hospital blueprint 默认触发 human review。
- blueprint 创建时写 `builder.blueprint.created` event。
- 审核 approve 后写入 `generated_projects` 和首个 `project_versions`。
- `generated_project.manifest.files` 记录预期项目文件清单。
- Phase 5.2 approve 后写入真实项目文件到 `PROJECT_WORKSPACE_ROOT/<project_id>/`。
- 文件生成器只允许相对路径，禁止绝对路径和 `..`。
- 单文件大小受 `MAX_GENERATED_FILE_BYTES` 限制。
- `project_versions.manifest` 记录真实文件路径、字节数和 sha256。
- Phase 5.3 生成后写 `project_validations`。
- 第一版 validation 包含 storage path、必需文件、sha256、bytes、Python compile 检查。
- validation 完成写 `project.validation.completed` event。
- `/v1/generated-projects/{project_id}/validations` 可查询校验结果。
- Phase 5.4 validation 增加受控命令执行。
- 命令白名单第一版：
  - `python -m compileall app tests`
  - `python -m pytest tests`
- 命令 cwd 固定为生成项目目录。
- 不使用 shell。
- timeout 使用 `MAX_TOOL_TIMEOUT_SECONDS`。
- stdout / stderr 只保存截断摘要。
- Phase 5.5 生成后写 `project_eval_reports`。
- eval report 检查生产级 Agent 必需能力：
  - RAG grounded answer 和 no-answer policy。
  - 三层 memory。
  - human review gates。
  - RBAC、安全、审计。
  - PostgreSQL + pgvector + tenant isolation。
  - 测试策略。
  - observability。
  - runtime validation 是否通过。
- eval 完成写 `project.eval.completed` event。
- `/v1/generated-projects/{project_id}/eval-reports` 可查询 eval 结果。
- Phase 5.6 增加修复循环。
- `/v1/generated-projects/{project_id}/repair` 会先重跑 active version validation。
- active version 已通过时默认不修复；`force=true` 可强制生成新版本。
- validation 失败时，用 project blueprint 重新生成文件。
- 修复会创建新的 `project_versions`。
- 修复后重新写 validation 和 eval report。
- 修复完成写 `project.repair.completed` event。
- 后续 Phase 5.7 增加 LLM patch-based 修复，而不是全量重写。

生成项目结构：

```text
generated_projects/<project_name>/
├── README.md
├── .env.example
├── docker-compose.yml
├── pyproject.toml
├── alembic.ini
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database/
│   ├── graph/
│   ├── agents/
│   ├── prompts/
│   ├── rag/
│   ├── memory/
│   ├── tools/
│   ├── human_review/
│   ├── observability/
│   └── security/
├── alembic/
├── tests/
└── docs/
```

必须覆盖知识点：

- Prompt 模板和版本。
- LangGraph 状态图。
- 条件路由。
- 子图。
- checkpoint。
- interrupt / resume。
- RAG 导入、切分、检索、重排、引用。
- 工具注册、schema、权限、错误处理。
- 短期记忆、摘要记忆、长期记忆。
- 用户管理和租户隔离。
- 数据库模型和迁移。
- 多 Agent supervisor。
- 安全拒答。
- 领域合规。
- trace、日志、审计。
- 单元测试、集成测试、评估用例。

代码生成质量门禁：

- 生成前必须有 blueprint。
- blueprint 必须通过 Pydantic 校验。
- 写文件前必须生成 file manifest。
- 高风险领域写文件前必须人工审核。
- 写文件只能发生在 `generated_projects/<project_name>/`。
- 生成后必须运行 `ruff check` 和 `pytest`。
- 失败结果必须写入 `project_validations`。

## 16. 法律和医疗领域边界

律所 Agent：

- 不能替代律师执业判断。
- 必须记录法域、时间、资料来源。
- 合同、诉讼、法律意见输出默认需要律师审核。
- 客户资料必须租户隔离和审计。

医院 Agent：

- 不能替代医生诊断。
- 必须识别急症并建议立即就医。
- 诊疗建议默认需要医生审核。
- 患者资料按敏感数据处理。
- 医疗建议必须带证据来源和安全提示。

结论：

平台能生成生产级工程代码。平台不能保证生成内容无需专业审核即可上线。

## 17. 工具层

工具类型：

- 内置工具：文件读写、项目生成、测试运行、RAG 检索。
- 业务工具：CRM、日程、邮件、案件系统、病历系统。
- 外部工具：HTTP API、MCP server、数据库查询。

工具规范：

```python
class ToolSpec(TypedDict):
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    risk_level: str
    requires_review: bool
    timeout_seconds: int
```

工具执行要求：

- 参数先校验。
- 权限先校验。
- 高风险先审核。
- 异常结构化返回。
- 结果落库。
- 工具执行必须设置 timeout。
- 工具结果超过大小限制时写文件存储，数据库只保存摘要和 URI。
- 默认禁用 shell 工具。需要项目生成时，仅开放受控命令白名单。

## 18. Prompt 设计

Prompt 文件：

```text
app/prompts/
├── router.md
├── answer.md
├── memory_extract.md
├── tool_planner.md
├── review_summary.md
├── builder/
│   ├── requirements.md
│   ├── domain_expert.md
│   ├── architecture.md
│   ├── data_model.md
│   ├── compliance.md
│   └── code_generation.md
└── domains/
    ├── law_firm.md
    └── hospital.md
```

要求：

- Router 输出 JSON。
- Builder 输出严格 schema。
- 高风险领域 Prompt 必须写拒答和审核边界。
- Answer 不得使用无来源专业结论。

第一版实现：

- `app/prompts/` 已作为版本化 prompt registry。
- `app/prompts/registry.py` 提供 `load_prompt` 和 `render_prompt`。
- prompt 路径做目录逃逸校验，禁止绝对路径、反斜杠和 `..`。
- `direct_answer` 使用 `app/prompts/answer.md` 组装 memory、RAG、用户输入。
- 领域策略 prompt 存放在 `app/prompts/domains/`。
- 生成项目会输出：
  - `app/prompts/answer.md`
  - `app/prompts/review_summary.md`
  - `app/prompts/domains/policy.md`
- 生成项目验证器将 prompt 文件列入 REQUIRED_FILES，避免生成“没有 prompt 资产”的伪生产项目。

## 19. 配置

`.env.example`：

```env
APP_ENV=local
APP_SECRET_KEY=

DATABASE_URL=postgresql+psycopg://agent:agent@localhost:5432/agent
REDIS_URL=redis://localhost:6379/0

MODEL_PROVIDER=openai_compatible
MODEL_ID=
BASE_URL=
API_KEY=
TEMPERATURE=0

EMBEDDING_MODEL=
EMBEDDING_BASE_URL=
EMBEDDING_API_KEY=

TRACE_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=

PROJECT_WORKSPACE_ROOT=./generated_projects
MAX_GENERATED_FILE_BYTES=200000
MAX_TOOL_TIMEOUT_SECONDS=120

DEFAULT_DAILY_TOKEN_LIMIT=100000
DEFAULT_MONTHLY_TOKEN_LIMIT=2000000
BUILDER_BLUEPRINT_TOKEN_LIMIT=80000
BUILDER_FULL_PROJECT_TOKEN_LIMIT=300000
TOKEN_COST_CURRENCY=USD

MODEL_GATEWAY_TIMEOUT_SECONDS=60
MODEL_GATEWAY_MAX_RETRIES=2
MODEL_GATEWAY_CIRCUIT_FAILURES=5

SECRET_ENCRYPTION_KEY_ID=local-dev
BACKUP_TARGET_URI=./backups
SSE_EVENT_RETENTION_HOURS=24

SANDBOX_NETWORK_ENABLED=false
SANDBOX_CPU_LIMIT=2
SANDBOX_MEMORY_MB=2048
SANDBOX_TIMEOUT_SECONDS=180
```

## 20. 安全设计

必须具备：

- 租户隔离。
- RBAC。
- API token 哈希存储。
- 敏感字段脱敏日志。
- 工具权限矩阵。
- 文件路径沙箱。
- Prompt injection 防护。
- RAG source allowlist。
- 生成代码安全扫描。

Prompt injection 基础策略：

- 文档内容永远是数据，不是系统指令。
- RAG 上下文不得覆盖 system prompt。
- 工具调用只接受结构化 plan，不接受文档中的调用指令。
- 高风险工具必须经过权限和审核双重检查。

## 21. 隐私与合规

必须具备：

- PII / PHI 检测。
- memory 写入前隐私过滤。
- 用户数据导出。
- 用户数据删除。
- 数据保留周期。
- 审计日志保留周期。
- 法律/医疗领域 consent 记录。
- 高风险领域回答保留证据链。

隐私规则：

- 敏感个人数据默认不写长期记忆。
- 医疗信息、法律案件信息默认标记 sensitive。
- 训练/评估数据集不得自动包含敏感原文。
- 反馈进入 eval 前必须脱敏。

## 22. 沙箱执行

生成项目的测试、lint、代码扫描必须在沙箱中执行。

沙箱要求：

- 只能访问项目 workspace。
- 默认禁止网络。
- 命令白名单。
- CPU、内存、磁盘、timeout 限制。
- 运行前清理环境变量中的 secret。
- 输出超过限制时截断并保存完整日志到文件存储。

允许命令第一版：

```text
pytest
ruff check
mypy
python -m compileall
```

禁止：

- 任意 shell。
- 删除 workspace 外文件。
- 访问用户 home。
- 读取真实 `.env`。
- 后台常驻进程。

## 23. 事件流

长任务必须支持 SSE 订阅。

事件类型：

```text
run.created
run.started
node.started
node.completed
node.failed
review.pending
review.decided
builder.blueprint.created
file.generated
validation.started
validation.completed
run.completed
run.failed
```

事件规则：

- 每个事件带 `run_id`、`tenant_id`、`event_id`、`created_at`。
- SSE 断线后可用 last event id 恢复。
- 事件 payload 不包含 secret。
- 大 payload 写数据库，SSE 只发送摘要。

## 24. 可观测性

必须记录：

- run id。
- user id。
- tenant id。
- graph name。
- node latency。
- route decision。
- RAG query 和 chunk ids。
- tool call 参数摘要。
- human review 状态。
- generated files。
- validation output。
- prompt tokens。
- completion tokens。
- embedding tokens。
- rerank tokens。
- estimated cost。

日志格式：JSON。

追踪：OpenTelemetry。

审计：PostgreSQL `agent_events`、`tool_calls`、`human_review_requests`。

## 25. 备份、恢复与运维

健康检查：

- `GET /healthz`: 进程活着。
- `GET /readyz`: DB、Redis、Model Gateway、worker 可用。

运维指标：

- API latency。
- graph node latency。
- worker queue depth。
- failed jobs。
- model error rate。
- token spend。
- review pending count。
- RAG no-answer rate。

告警：

- DB 不可用。
- Redis 不可用。
- worker heartbeat 超时。
- model provider 连续失败。
- token 异常消耗。
- review 积压。
- sandbox timeout 过高。

恢复：

- 数据库每日备份。
- generated project storage 每日备份。
- 支持 point-in-time recovery。
- 每月恢复演练。
- 备份结果写入 `backup_jobs`。

## 26. 评估体系

生产级 Agent 需要 eval，不只需要 pytest。

评估集：

- route eval：输入到 route 是否正确。
- RAG eval：召回是否命中 gold source。
- answer eval：回答是否基于证据。
- review eval：高风险动作是否触发审核。
- builder eval：生成项目是否包含必需模块。
- safety eval：法律/医疗越界问题是否拒答或转人工。
- token eval：复杂任务是否在预算内完成，超额时是否保存 partial result。

评估结果表：

```text
eval_runs
  id uuid primary key
  tenant_id uuid
  eval_name text
  status text
  metrics jsonb
  created_at timestamptz

eval_cases
  id uuid primary key
  eval_run_id uuid
  input jsonb
  expected jsonb
  actual jsonb
  score numeric
  passed boolean
  created_at timestamptz
```

## 27. 测试

测试层级：

- 单元测试：节点、服务、工具。
- 图测试：不同 route 完整运行。
- RAG 测试：召回、引用、无答案。
- 人审测试：interrupt、approve、reject、resume。
- 多 Agent 测试：artifact schema 和冲突合并。
- 生成项目测试：文件存在、导入成功、测试通过。
- 安全测试：越权、敏感数据、高风险拒答。

命令：

```bash
pytest
ruff check .
mypy app
```

## 28. 目录结构

```text
langgraph_product/
├── pyproject.toml
├── docker-compose.yml
├── alembic.ini
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   ├── auth/
│   ├── database/
│   ├── graph/
│   ├── agents/
│   ├── builder/
│   ├── knowledge/
│   ├── memory/
│   ├── model_gateway/
│   ├── tools/
│   ├── human_review/
│   ├── artifacts/
│   ├── sandbox/
│   ├── templates/
│   ├── feedback/
│   ├── observability/
│   ├── security/
│   └── workers/
├── prompts/
├── alembic/
├── tests/
├── evals/
└── generated_projects/
```

## 29. MVP 裁剪

第一版不做：

- 前端页面。
- OAuth / SSO。
- 多区域部署。
- 分布式锁复杂编排。
- 专用向量数据库。
- 自动上线部署。

第一版必须做：

- API + CLI。
- PostgreSQL + pgvector。
- Redis + RQ worker。
- 用户、租户、会话。
- token 额度和用量追踪。
- Model Gateway。
- 幂等 key。
- 长期记忆。
- RAG。
- LangGraph checkpoint。
- Human review。
- Agent Builder blueprint。
- 生成项目文件。
- 生成项目版本。
- 沙箱验证。
- SSE 运行事件。
- domain template registry。
- 生成后验证。

## 30. 实施阶段

### Phase 1：生产底座

- FastAPI。
- PostgreSQL + pgvector。
- SQLAlchemy models。
- Alembic migrations。
- 用户和租户上下文。
- Agent run/event 落库。
- RQ worker。
- 基础 API。
- token quota tables。
- token usage events。
- idempotency tables。
- secret tables。
- health endpoints。

Phase 11 Alembic 实现：

- `alembic.ini` 固定迁移入口。
- `alembic/env.py` 从 `app.config.settings.database_url` 读取运行时数据库 URL。
- `target_metadata = Base.metadata`，支持后续 autogenerate。
- `alembic/versions/0001_initial_schema.py` 创建当前 SQLAlchemy model schema。
- `pyproject.toml` 增加 `alembic` 依赖。
- 本地开发仍保留 `init_db()` 的 `create_all` 兼容路径；生产部署应执行 `alembic upgrade head`。

### Phase 12：Secrets 管理

第一版实现：

- `secrets` 表保存租户级 secret。
- API：
  - `POST /v1/secrets`
  - `GET /v1/secrets`
- secret 写接口仅 `admin` / `owner` 可调用。
- API 响应不返回明文 secret，只返回 metadata 和 `value_sha256`。
- 新版本 secret 写入后，旧 active 版本标记为 `rotated`。
- 本地实现使用 `APP_SECRET_KEY` 派生的 reversible 加密流，避免开发数据库明文存储。
- 生产部署应替换为 KMS / Vault adapter，保持服务边界不变。

### Phase 13：Tool Calls 审计

第一版实现：

- `tool_calls` 表记录工具调用审计。
- API：
  - `POST /v1/tool-calls`
  - `GET /v1/tool-calls`
- 字段包含 tenant、run、tool_name、risk_level、status、input/output summary、error、metadata、started/finished。
- 写入和读取要求 Bearer token，角色为 `admin` / `owner` / `reviewer`。
- terminal status 自动写 `finished_at`，便于延迟和失败审计。

后续增强：

- 将 LangGraph tool executor 的每次真实执行自动写入 `tool_calls`。
- 按工具 allowlist 执行受控命令。
- 对 medium/high risk tool call 强制进入 human review。

### Phase 14：Background Jobs / Worker

为避免平台继续膨胀，Phase 14 只保留后台任务的最小生产边界：

- `background_jobs` 表记录异步任务状态。
- API：
  - `POST /v1/jobs`
  - `GET /v1/jobs`
  - `GET /v1/jobs/{job_id}`
- job API 要求 `admin` / `owner` Bearer token。
- `app/worker.py` 提供 RQ worker 入口。
- `pyproject.toml` 增加 `redis`、`rq` 依赖。
- 当前不继续展开复杂调度；后续只在文档导入、embedding、项目验证确实需要异步时接入队列。

### Phase 2：LangGraph Runtime

- AgentState。
- 主图。
- checkpoint。
- router。
- answer。
- trace。
- PostgreSQL checkpoint。
- run budget enforcement。
- Model Gateway。
- retry/fallback/timeout。

### Phase 7：Model Gateway + Budget Enforcement

第一版实现：

- `model_providers` 管理供应商。
- `model_registry` 管理模型、role、context window、成本和能力标记。
- 启动时 seed `local_stub` provider 和 `cheap_chat` / `builder` / `embedding` 默认模型。
- `GET /v1/model-providers`、`POST /v1/model-providers`。
- `GET /v1/model-registry`、`POST /v1/model-registry`。
- Runtime 在 graph 执行前读取用户 token quota，额度不足则返回 `quota_exceeded`，不调用模型，不写 token usage。
- Runtime 按 role 选择 active 模型，并注入 graph state。
- ModelGateway 返回 provider/model/token 信息。
- Runtime 将模型调用写入 `token_usage_events` 并扣减用户额度。
- Phase 7.2 支持 OpenAI-compatible provider。
- Provider 类型：
  - `stub`：本地默认，无需网络和 API key。
  - `openai_compatible`：通过 OpenAI SDK 调用兼容 Chat Completions 的服务。
- ModelGateway 支持 active 模型候选 fallback：
  - 优先使用最新 active model。
  - 当前候选失败时自动尝试同 role 的下一个 active model。
  - `token_usage_events.metadata_json` 记录 attempts、provider_type、failed_over。
- ModelGateway 根据模型 `input_cost_per_1k` / `output_cost_per_1k` 写入 `estimated_cost`。
- 所有模型候选都失败时，runtime 将 run 标记为 `failed`，落 `run.failed.model_gateway` 事件。

后续增强：

- Embedding provider 真实调用。
- 更细的 retry、timeout、circuit breaker。
- Grant 优先扣减和过期 grant 回收。
- 多 Agent builder 的 per-specialist budget。

### Phase 3：Memory + RAG

- chat_sessions。
- chat_messages。
- user_memories。
- knowledge_bases。
- document_chunks。
- hybrid retrieval。
- memory embedding。
- embedding token usage。

### Phase 4：Human Review

- review tables。
- interrupt / resume。
- approve/revise/reject。
- 高风险工具拦截。
- review API。
- SSE review events。

### Phase 5：Multi-Agent Builder

- supervisor graph。
- specialist agents。
- blueprint schema。
- code generation。
- validation。
- generated project storage。
- project versions。
- per-agent token budget。
- partial artifact on budget stop。
- sandbox validation。

### Phase 6：领域模板

- law_firm template。
- hospital template。
- compliance rules。
- sample tests。
- eval cases。
- template registry。
- feedback loop。

第一版实现：

- `app/domain_templates.py` 内置默认模板。
- 启动时幂等写入 `domain_templates`。
- `POST /v1/domain-templates/defaults/seed` 可手动重新 seed。
- `GET /v1/domain-templates` 返回全局模板和租户模板。
- `GET /v1/domain-templates/{template_id}` 返回完整模板详情。
- `law_firm` 模板包含：
  - attorney-client privileged 数据标记。
  - legal advice / external send / case lookup 人审规则。
  - 律所默认 system / review / no-answer prompt。
  - 法律意见人审、无证据拒答、敏感数据审计 eval cases。
- `hospital` 模板包含：
  - PHI 数据标记。
  - medical advice / patient record lookup / care plan change 人审规则。
  - 医院默认 system / review / no-answer prompt。
  - 临床建议人审、PHI 访问审计、无证据拒答 eval cases。
- Builder blueprint 自动带 `domain_template` section。
- Security section 合入模板 compliance profile。
- Eval 增加 `domain_template_coverage` 检查。
- Phase 6.2 支持租户自定义模板覆盖。
- `POST /v1/domain-templates` 可创建租户模板。
- `POST /v1/builder/runs` 支持 `domain_template_id`。
- 指定模板时，builder blueprint 优先使用该模板的 required modules、prompts、eval cases、compliance profile。
- Phase 6.3 支持模板版本和反馈闭环。
- 创建同一租户、同一 domain、同一 name 的新 active 模板时，旧 active 版本自动标记 `deprecated`。
- `PATCH /v1/domain-templates/{template_id}/status` 支持 `active`、`deprecated`、`archived`。
- `GET /v1/domain-templates/{template_id}/improvement-suggestions` 汇总反馈和失败 eval，返回模板改进建议。
- 改进建议不自动改模板，必须由管理员创建新版本。
- Phase 6.4 支持模板审批流。
- 全局默认模板由平台 seed 后直接 `active`。
- 租户创建 `risk_level=high` 或 `law_firm` / `hospital` 等高风险模板时，初始状态为 `pending_review`。
- `GET /v1/domain-templates/pending` 返回租户待审模板。
- `POST /v1/domain-templates/{template_id}/review` 由 `owner` / `admin` 审批：
  - `approve`：模板变为 `active`，同租户同 domain/name 的旧 active 版本变为 `deprecated`。
  - `reject`：模板变为 `rejected`，不可被 builder 使用。
- Builder runtime 只允许使用 `active` 且租户匹配的模板；未审批、拒绝、归档模板都会被拒绝。

## 31. 验收标准

第一版通过标准：

- 用户、租户、会话数据落库。
- 写接口支持幂等。
- 用户和租户 token 额度可查询。
- 管理员可发放 token grant。
- LLM、embedding、rerank token 用量可追踪。
- 长期记忆可写入、读取、禁用。
- RAG 使用 PostgreSQL + pgvector。
- 主图能 direct、rag、tool、builder 路由。
- 高风险动作触发人工审核。
- 人工审核可 resume。
- 多 Agent 生成领域 Agent 蓝图。
- 生成项目可写入目录。
- 生成项目有 version snapshot。
- 生成项目可 rollback。
- 生成项目测试可运行。
- 测试运行在 sandbox。
- 所有 Agent run 可回放。
- 所有长任务可通过 run_id 查询状态。
- SSE 可订阅 run 事件。
- Builder 超预算会停止并保存 partial result。
- 人审 reject/revise/approve 三条路径都有测试。
- 生成项目只能写入 workspace。
- 至少一套 law_firm 和 hospital blueprint eval 通过。
- `/healthz`、`/readyz` 可用。
- secret 不进入 trace、checkpoint、generated files。

## 32. 关键决策

1. `langgraph_product` 是独立生产项目，不依赖学习目录。
2. PostgreSQL + pgvector 是默认生产存储。
3. Redis + RQ 用于缓存和后台任务。
4. LangGraph checkpoint 必须启用，支撑人审和恢复。
5. 高风险领域默认人工审核。
6. 多 Agent 使用 Supervisor + Specialist 子图。
7. Agent Builder 生成工程代码，不承诺免审专业结论。
8. 第一版不做前端，先做 API、CLI、worker、测试。
9. Token 是一等资源，所有模型调用必须记录、扣减、可审计。
10. 模型调用必须通过 Model Gateway。
11. 生成项目必须版本化、可回滚、可验证。
12. 运行生成代码必须使用沙箱。
13. 写操作必须具备幂等能力。



