# AgentSkillTools

这是一个面向 AI Agent 进阶学习与生产级项目实践的工作区。每个子文件夹都是一个独立学习项目，文件夹名代表学习主题：Prompt、RAG、MCP、LangChain Memory、LangGraph Agent。

项目目标不是堆 demo，而是通过每个独立项目理解生产级 Agent 的关键能力。最终真正上线和持续迭代的项目放在 `langgraph_product` 中生成，其他目录主要承担学习、验证、沉淀方案和提供参考实现的作用。

## 项目结构

```text
AgentSkillTools/
├── prompt_product/       # 基于关键词生成可保存的 Prompt 草稿
├── rag_product/          # 面向生产知识库的 RAG 能力，规划短/中/长文本三条路线
├── mcp_product/          # 手写 MCP 服务端与客户端，沉淀工具调用协议理解
├── langchain_product/    # 基于 LangChain 的短期/中期/长期记忆实现
├── langgraph_product/    # 基于 LangGraph 的 Agent 图编排项目雏形
├── docs/                 # 项目推进文档
└── requirements.txt
```

## 当前学习项目

| 项目 | 学习主题 | 当前状态 | 下一步重点 |
| --- | --- | --- |
| `prompt_product` | Prompt 工程与 Prompt 草稿生成 | 已实现 OpenAI-compatible 客户端、工具 schema、Prompt 生成与文件追加保存 | 抽象 Prompt 模板、增加版本管理和质量评分 |
| `rag_product` | RAG 知识库 | 当前主要是文本切分和 Chroma 方向的预研注释 | 建立短/中/长文本 RAG 学习路线和 MVP |
| `mcp_product` | MCP 服务端和客户端 | 已实现 stdio MCP 服务端、客户端连接、工具列表获取、工具规划调用雏形 | 修正工具链规划、补真实工具、增加错误处理和测试 |
| `langchain_product` | LangChain Memory | 已实现 SQLite 持久化会话、摘要压缩、长期记忆抽取 | 对比 LangGraph memory，沉淀记忆系统设计经验 |
| `langgraph_product` | LangGraph Agent 上线项目 | 已有主图调用子图的基础示例 | 在这里生成最终 Agent 项目：状态、路由、工具、RAG、记忆闭环 |

## 文档入口

- [项目蓝图](docs/PROJECT_BLUEPRINT.md)
- [系统架构](docs/ARCHITECTURE.md)
- [学习项目说明](docs/MODULES.md)
- [RAG 分层方案](docs/RAG_STRATEGY.md)
- [开发路线图](docs/ROADMAP.md)
- [运行手册](docs/RUNBOOK.md)
- [决策记录](docs/DECISIONS.md)

## 本地运行

建议使用 Python 虚拟环境：

```bash
pip install -r requirements.txt
```

根目录 `.env` 用于配置模型和外部服务。当前代码中存在两套命名：

```env
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL_ID=

API_KEY=
BASE_URL=
MODEL_ID=
MODEL_PROVIDER=
TEMPERATURE=0

SERPER_API_KEY=
DATABASE_URL=sqlite:///chat_memory.db
```

`langgraph_product` 是独立子项目，启动时需要将它作为工作目录。使用仓库根目录的普通 Python 虚拟环境即可，不需要 uv：

```powershell
\.venv\Scripts\Activate.ps1
Set-Location .\langgraph_product
python -m uvicorn app.main:app --reload
```

启动后访问 `http://127.0.0.1:8000/healthz`，应返回 `{"status":"ok"}`。

常用入口：

```bash
python -m prompt_product.llm
python -m mcp_product.client
python -m langchain_product.memory.debug_runner
python -m langchain_product.memory.debug_runner
```

## 推进原则

1. 每个文件夹都是独立学习项目，名字是什么就学习什么。
2. 每个学习项目先形成自己的最小可用闭环，避免过早互相耦合。
3. 最终上线项目只在 `langgraph_product` 中生成，其他项目提供经验、方案和参考代码。
4. 文档和代码同步演进，重要设计变化记录到 `docs/DECISIONS.md`。
