# RAG 生产调用方式

`rag_product` 是独立学习项目，但它需要让你看清楚生产中 RAG 到底如何被 Agent 调用。生产里通常不会把整篇文档塞进 Prompt，而是让 Agent 在需要知识时调用一个稳定的 RAG 能力。

当前实现的长文本链路是：

```text
Document
  │
  ├─ section_summary chunks：章节级路由
  │
  └─ leaf chunks：章节内证据

Query
  │
  ├─ 检索 section_summary，得到候选章节
  ├─ 只在候选章节内检索 leaf chunks
  ├─ 用 embedding score + lexical overlap 做轻量重排
  └─ 输出带 source / section / location / score 的上下文
```

## 推荐判断

| 调用方式 | 适合场景 | 优点 | 风险 |
| --- | --- | --- | --- |
| LangGraph 节点 | 固定业务流程、强可控 Agent | 稳定、可观测、容易测试 | 灵活性较低 |
| MCP Tool | 希望 Agent 自主决定是否检索 | 符合工具调用范式 | 依赖 Prompt 约束 |
| HTTP API | 多服务、多 Agent、前后端共用知识库 | 边界清晰、可独立部署 | 需要服务治理 |

你的最终项目在 `langgraph_product` 中生成，优先建议使用 LangGraph 节点调用。等需要跨项目复用时，再把 RAG 独立成 HTTP API 或 MCP Tool。

## 方式一：LangGraph 节点调用

这是最适合最终 Agent 项目的方式。图负责判断是否需要 RAG，RAG 节点只负责返回知识上下文。

```python
from typing import TypedDict

from rag_product.runtime import build_rag_context_for_agent


class AgentState(TypedDict):
    user_input: str
    need_rag: bool
    rag_context: str
    final_answer: str


def retrieve_knowledge(state: AgentState) -> dict:
    if not state.get("need_rag", False):
        return {"rag_context": ""}

    context = build_rag_context_for_agent(
        query=state["user_input"],
        top_k=5,
    )
    return {"rag_context": context}
```

回答节点应该遵守知识边界：

```python
def answer_with_rag(state: AgentState) -> dict:
    prompt = f'''
你是一个严谨的知识库问答助手。

只能基于【知识库上下文】回答问题。
如果上下文中没有答案，明确说明“当前知识库没有相关信息”。
回答时保留来源编号，例如 [1]、[2]。

【知识库上下文】
{state["rag_context"]}

【用户问题】
{state["user_input"]}
'''
    answer = model.invoke(prompt)
    return {"final_answer": str(answer)}
```

## 方式二：作为 MCP Tool 调用

如果你希望 Agent 自己决定什么时候检索，可以把 RAG 包成工具：

```python
from rag_product.runtime import build_rag_context_for_agent


@mcp.tool()
def search_knowledge_base(query: str, top_k: int = 5) -> str:
    """
    查询业务知识库，返回和用户问题最相关的知识片段。
    当用户问题涉及项目文档、业务规则、产品说明、历史资料时使用。
    """
    return build_rag_context_for_agent(query=query, top_k=top_k)
```

Agent 的系统 Prompt 要明确写：

```text
当用户问题涉及业务知识、项目文档、规则、产品说明或历史资料时，必须先调用 search_knowledge_base。
不要凭模型记忆回答知识库问题。
如果工具返回“没有检索到相关内容”，必须说明当前知识库没有相关信息。
```

## 方式三：作为 HTTP API 服务调用

当 RAG 要被多个 Agent、前端页面或后端服务共用时，建议独立成服务。

启动服务：

```bash
uvicorn rag_product.api:app --host 127.0.0.1 --port 8001
```

导入文档：

```bash
curl -X POST http://127.0.0.1:8001/rag/ingest \
  -H "Content-Type: application/json" \
  -d "{\"file_path\":\"rag_product/README.md\"}"
```

检索结构化结果：

```bash
curl -X POST http://127.0.0.1:8001/rag/search \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"生产级 Agent 如何获取 RAG\",\"top_k\":5}"
```

获取可直接注入 Agent Prompt 的上下文：

```bash
curl -X POST http://127.0.0.1:8001/rag/agent-context \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"生产级 Agent 如何获取 RAG\",\"top_k\":5}"
```

Agent 项目中调用：

```python
import requests


def retrieve_knowledge_from_service(query: str, top_k: int = 5) -> str:
    response = requests.post(
        "http://127.0.0.1:8001/rag/agent-context",
        json={"query": query, "top_k": top_k},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["context"]
```

## 生产级 RAG 最少要记录什么

真正上线时，每次 RAG 调用建议记录：

- `query`: 用户原始问题。
- `rewritten_query`: 改写后的检索问题。
- `top_k`: 召回数量。
- `chunk_ids`: 命中的 chunk。
- `scores`: 相似度或 rerank 分数。
- `sources`: 引用来源。
- `section_title`: 长文本命中的章节。
- `location`: 章节和 chunk 位置，例如 `section:2/chunk:4`。
- `answer`: 最终答案。
- `latency_ms`: 检索耗时。

这些记录后续用于调试“为什么没搜到”“为什么答错了”“哪个文档污染了答案”。

## 当前项目和生产项目的关系

`rag_product` 用来学会 RAG 工程，`langgraph_product` 才是最终上线项目所在地。建议路线：

1. 先在 `rag_product` 中把 ingest、embedding、search、context 跑通。
2. 用 `python -m rag_product.cli validate` 验证长文本路由和证据召回。
3. 再把 `build_rag_context_for_agent()` 的思想迁移到 `langgraph_product` 的 RAG 节点。
4. 如果最终项目变复杂，再把 RAG 做成 HTTP API 或 MCP Tool。
