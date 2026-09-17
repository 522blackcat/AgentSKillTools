# 系统架构

## 当前架构

```text
OpenAI-compatible / Ollama Model
           │
           ├──────── prompt_product
           │             ├─ build_system_prompt()
           │             ├─ function_to_json()
           │             └─ write_prompt_add_file()
           │
           ├──────── mcp_product
           │             ├─ MCPServer tools
           │             └─ MCPClient stdio session
           │
           ├──────── langchain_product
           │             ├─ DatabaseChatMessageHistory
           │             ├─ SummaryMemoryAssistant
           │             └─ UserMemoryExtractor
           │
           └──────── langgraph_product
                         ├─ main graph
                         └─ sub graph
```

## langgraph_product 目标架构

```text
User
 │
 ▼
Agent Graph (langgraph_product)
 │
 ├─ Intent Router
 │    ├─ prompt generation
 │    ├─ knowledge QA
 │    ├─ tool task
 │    └─ chat / planning
 │
 ├─ Memory Adapter
 │    ├─ recent messages
 │    ├─ summary memory
 │    └─ long-term facts
 │
 ├─ RAG Adapter
 │    ├─ short text index
 │    ├─ medium text index
 │    └─ long text index
 │
 ├─ MCP Adapter
 │    ├─ local tools
 │    ├─ external APIs
 │    └─ file/report tools
 │
 └─ Response Composer
      ├─ answer
      ├─ citations
      ├─ tool results
      └─ memory updates
```

## 学习项目到最终项目的迁移方式

`prompt_product`、`rag_product`、`mcp_product`、`langchain_product` 不默认作为最终项目的运行时依赖。它们更像实验室：先独立把主题学清楚，再把成熟设计迁移到 `langgraph_product`。

推荐迁移方式：

- 先在独立项目里验证最小闭环。
- 总结稳定的数据结构、接口和失败经验。
- 在 `langgraph_product` 中按最终 Agent 的需要重写或抽取。
- 保留独立项目，继续作为学习笔记和实验环境。

## 最终项目接口建议

### Prompt Adapter

```python
class PromptGenerator:
    def generate(self, keyword: str, save: bool = True) -> str:
        ...
```

### RAG Adapter

```python
class KnowledgeBase:
    def ingest(self, document: str, metadata: dict) -> str:
        ...

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        ...

    def answer(self, query: str) -> dict:
        ...
```

### Memory Adapter

```python
class MemoryService:
    def load_context(self, user_id: str, session_id: str, query: str) -> dict:
        ...

    def save_turn(self, user_id: str, session_id: str, user_input: str, assistant_output: str) -> None:
        ...
```

### MCP Adapter

```python
class ToolRuntime:
    async def list_tools(self) -> list[dict]:
        ...

    async def call_tool(self, name: str, arguments: dict) -> str:
        ...
```

## 数据层

当前已有 SQLite：

- `chat_sessions`: 会话历史与摘要。
- `user_memories`: 长期用户事实。

建议后续新增：

- `documents`: 文档元数据。
- `chunks`: 切分后的文本块。
- `retrieval_logs`: 每次检索的 query、命中文档、得分、最终答案。
- `agent_runs`: Agent 每次运行的节点轨迹和工具调用记录。

## 配置层

当前项目里模型配置有两套命名：

- `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL_ID`
- `API_KEY` / `BASE_URL` / `MODEL_ID` / `MODEL_PROVIDER`

建议后续在 `langgraph_product` 中收敛自己的配置模块，例如 `settings.py`。其他学习项目可以保留各自配置，方便独立实验。
