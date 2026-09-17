# 06 LLM 配置与 Graph 流程验收

这份文档回答两个问题：

1. 主平台的 LLM 如何配置，在哪里真正调用。
2. 生成出来的律所/医院 Agent 是否能看到自己的 LLM 配置和 Graph 流程。

## 一、主平台 LLM 配置在哪里

主平台有两层模型配置。

### 1. 运行环境配置

文件：

```text
.env.example
app/config.py
```

关键变量：

```text
MODEL_PROVIDER=openai_compatible
MODEL_ID=
BASE_URL=
API_KEY=
TEMPERATURE=0
```

本地学习可以不填真实 `API_KEY`，使用 stub/fallback 路径跑通流程。

### 2. 数据库模型注册表

主平台支持通过 API 注册模型供应商和模型：

```text
POST /v1/model-providers
POST /v1/model-registry
GET  /v1/model-registry
```

代码位置：

```text
app/services.py
```

运行时会按角色选择模型，例如：

```text
cheap_chat
```

这样做的原因是：生产项目里通常不是所有节点都用同一个模型。便宜模型可以做路由、摘要、普通问答；强模型可以做复杂规划、代码生成、合规分析。

## 二、主平台 LLM 在哪里真正调用

调用链：

```text
POST /v1/chat/runs/{run_id}/invoke
POST /v1/builder/runs/{run_id}/invoke
  -> app/main.py
  -> app/runtime.py
  -> app/graph/builder.py
  -> app/graph/nodes.py
  -> app/model_gateway/gateway.py
```

关键点：

- `app/runtime.py` 负责读取数据库中的模型注册表。
- `app/runtime.py` 把模型 provider、model_id、base_url、api_key、fallback models 注入 graph state。
- `app/graph/nodes.py` 中的节点构造 `ModelRequest`。
- `app/model_gateway/gateway.py` 统一执行 stub 或 OpenAI-compatible 调用。
- token 用量和费用估算会写入 `token_usage_events`。

也就是说，主平台不是只在文档里写了 LLM 配置，而是 runtime -> graph node -> model gateway 这条链路实际接上了。

## 三、生成出来的律所 Agent 是否有自己的 LLM 配置

现在生成项目会包含：

```text
.env.example
app/settings.py
app/llm/gateway.py
app/graph.py
```

生成项目里的 `.env.example` 会包含：

```text
MODEL_PROVIDER=openai_compatible
MODEL_ID=
BASE_URL=
API_KEY=
```

生成项目里的 `app/settings.py` 会读取这些变量。

生成项目里的 `app/llm/gateway.py` 是模型调用边界：

- 本地默认 `stub`
- 配置 `API_KEY` 后可走 `openai_compatible`
- 业务 graph 不直接依赖供应商 SDK

## 四、生成出来的律所 Agent 是否有 Graph 流程

生成项目里的 `app/graph.py` 会生成真正的 LangGraph `StateGraph`，并显式包含核心节点：

```text
input_guard
load_memory
intent_router
retrieve_knowledge
answer
human_review
persist_audit
```

并暴露：

```text
route_intent(...)
agent_graph
invoke_graph(...)
```

`invoke_graph(...)` 会调用 `agent_graph.invoke(...)`，因此它不是只写了流程合约，而是实际通过 LangGraph 运行。

它已经具备生产项目应该能看到的关键结构：

- 路由
- RAG：embedding、pgvector 检索、evidence context、citation validation
- LLM 调用边界
- 人工审核判断
- 审计节点

后续如果要继续加强“生成出来的项目”，优先方向应该是扩充生成项目内部的真实节点实现，例如数据库读写、真实 RAG 检索、真实人工审核队列，而不是继续扩主平台外围。

## 五、如何验收

主平台验收：

```powershell
pytest tests/test_phase7_model_gateway.py
```

生成项目验收：

```powershell
pytest tests/test_phase5_multi_agent_builder.py tests/test_phase8_prompts.py
```

全量验收：

```powershell
pytest tests
```

当前测试会确保：

- 主平台能注册模型 provider/model。
- runtime 会选择模型并记录 token usage。
- 模型失败时可以 fallback。
- 生成项目必须包含 LLM gateway。
- 生成项目必须包含可执行的 LangGraph StateGraph。
