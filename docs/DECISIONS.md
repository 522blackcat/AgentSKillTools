# 决策记录

这里记录项目推进过程中的重要设计决策。每条记录建议包含：日期、背景、决策、影响。

## 2026-09-15：按五个独立学习项目组织 Agent 学习路线

背景：

当前项目已经自然拆分成 Prompt、RAG、MCP、LangChain Memory、LangGraph 五个目录。用户明确：每个项目是独立的，文件夹名叫什么就是学习什么，最终上线项目在 `langgraph_product` 中生成。

决策：

保持五个子项目独立演进。`prompt_product`、`rag_product`、`mcp_product`、`langchain_product` 主要用于学习和验证；最终上线项目只在 `langgraph_product` 中生成。

影响：

- 每个学习项目先完成自己的闭环。
- 不把其他目录默认当成 `langgraph_product` 的运行时依赖。
- 成熟经验可以迁移或重写进 `langgraph_product`。

## 2026-09-15：RAG 按文本长度拆成三条路线

背景：

短文本、中文本、长文本在切分、召回、上下文组织上的策略明显不同。

决策：

`rag_product` 同时支持短文本、中文本、长文本三种策略，由文本长度和文档结构自动选择。

影响：

- 短文本可以整文或小块检索。
- 中文本优先标题层级切分。
- 长文本需要层级索引和摘要索引。

## 2026-09-15：Memory 先保留 LangChain 学习项目，再向 LangGraph 最终项目迁移

背景：

当前 `langchain_product` 已经具备持久化历史、摘要压缩、长期记忆抽取。

决策：

不重写现有 Memory 学习代码，先在 `langchain_product` 中理解 MemoryService 设计，再在 `langgraph_product` 的最终 Agent 中按需迁移或重写。

影响：

- 降低迁移成本。
- 保留已有 SQLite 数据层。
- 后续可以逐步替换为 LangGraph 官方 memory/store 模式。
