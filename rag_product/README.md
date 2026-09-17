# rag_product

这是一个独立的 RAG 工程训练项目。目标是让你真正理解生产级 AI Agent 如何使用知识库，而不是只知道“把文档丢进向量库再问问题”。

## 学习目标

这个项目覆盖 RAG 的核心链路：

1. 本地加载文档。
2. 按文本长度选择切分策略。
3. 调用 embedding 模型生成向量。
4. 写入本地向量库。
5. 根据用户问题检索相关 chunk。
6. 把检索结果组装成 Agent 可使用的上下文。

## 文本长度策略

| 类型 | 长度 | 训练重点 |
| --- | --- | --- |
| 短文本 | 1000-5000 字 | 少切分，尽量保持完整语义 |
| 中文本 | 5000-30000 字 | 段落切分、适量 overlap、保留来源 |
| 长文本 | 30000 字以上 | 章节路由、父子 chunk、候选章节内精检 |

当前代码已经实现短/中/长自动分类。长文本不再只是把 chunk 调大，而是会生成两层索引：

- `section_summary`: 每个章节一个摘要路由 chunk，用来先判断问题属于哪些章节。
- `leaf`: 章节内的段落窗口 chunk，用来提供最终回答证据。

检索时先召回相关章节，再只在候选章节内召回具体证据 chunk，并用少量关键词 overlap 做重排补偿。这样更接近生产 RAG 的常见形态：粗召回负责不漏章，精召回负责不塞噪声。

## Embedding 配置

默认使用 `hash` provider，不依赖外部模型，方便先学习 RAG 机制。

```env
RAG_EMBEDDING_PROVIDER=hash
```

使用本地 Ollama embedding：

```env
RAG_EMBEDDING_PROVIDER=ollama
RAG_EMBEDDING_BASE_URL=http://localhost:11434
RAG_EMBEDDING_MODEL=nomic-embed-text
```

使用 OpenAI-compatible embedding 服务：

```env
RAG_EMBEDDING_PROVIDER=openai_compatible
RAG_EMBEDDING_BASE_URL=http://localhost:8000/v1
RAG_EMBEDDING_API_KEY=EMPTY
RAG_EMBEDDING_MODEL=text-embedding-3-small
```

## 运行

导入文档：

```bash
python -m rag_product.cli ingest docs/RAG_STRATEGY.md
```

检索：

```bash
python -m rag_product.cli search "长文本 RAG 应该怎么切分"
```

生成 Agent 可注入上下文：

```bash
python -m rag_product.cli context "生产级 Agent 如何获取 RAG"
```

生成一个可测试的长文档：

```bash
python -m rag_product.cli demo-long-text docs/long_rag_demo.md
python -m rag_product.cli ingest docs/long_rag_demo.md
python -m rag_product.cli search "什么时候应该使用章节摘要路由？"
```

运行确定性验证：

```bash
python -m rag_product.cli validate
```

验证脚本会临时生成 30000 字以上的长文档，检查：

- 是否进入 `long` 策略。
- 是否生成 `section_summary` 和 `leaf` 两类 chunk。
- 典型问题是否能命中预期章节。
- 返回上下文是否带 `source`、`section`、`location` 和 `score`。

## 生产调用

本项目已经提供三种生产调用形态：

- Python runtime：[runtime.py](C:/Users/200没有5/Desktop/AiAgentStudy/AgentSkillTools/rag_product/runtime.py)
- FastAPI 服务：[api.py](C:/Users/200没有5/Desktop/AiAgentStudy/AgentSkillTools/rag_product/api.py)
- 生产调用说明：[PRODUCTION_USAGE.md](C:/Users/200没有5/Desktop/AiAgentStudy/AgentSkillTools/rag_product/PRODUCTION_USAGE.md)

启动 RAG API：

```bash
uvicorn rag_product.api:app --host 127.0.0.1 --port 8001
```

最终的 `langgraph_product` 推荐先使用 Python runtime 方式接入：

```python
from rag_product.runtime import build_rag_context_for_agent

context = build_rag_context_for_agent("生产级 Agent 如何获取 RAG", top_k=5)
```

## 生产级 Agent 如何获取 RAG

生产级 Agent 不应该在主 Prompt 里塞入整个知识库，而应该通过 RAG 节点或 RAG 工具获取上下文：

```text
User Query
  │
  ▼
Agent Router
  │
  ├─ 不需要知识库：直接回答
  │
  └─ 需要知识库：
       1. query rewrite
       2. route to candidate sections
       3. retrieve leaf chunks inside candidate sections
       4. rerank
       5. build context with citations
       6. answer only from retrieved context
```

在最终的 `langgraph_product` 中，RAG 更适合作为一个节点：

```python
def retrieve_knowledge(state: AgentState) -> dict:
    context = rag_engine.build_agent_context(state["user_input"], top_k=5)
    return {"rag_context": context}
```

也可以作为一个 MCP tool 暴露给 Agent：

```python
search_knowledge_base(query: str, top_k: int = 5) -> str
```

节点方式适合稳定业务链路，工具方式适合让 Agent 自主决定是否检索。

## 当前工程边界

- 这是学习项目，不直接作为最终上线项目。
- 最终上线项目在 `langgraph_product` 里生成。
- 本项目沉淀 RAG 工程经验：切分、向量化、检索、引用、上下文构造。
