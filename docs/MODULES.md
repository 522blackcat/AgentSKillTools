# 学习项目说明

## prompt_product

定位：根据关键词生成完整 Prompt 草稿，并通过工具调用写入本地文件。

已有能力：

- `SYSTEM_PROMPT_TEMPLATE` 定义了 Prompt 生成规则。
- `build_system_prompt()` 将 Python 工具转换为模型可理解的工具 schema。
- `Agent` 使用 OpenAI-compatible API 调用模型。
- `write_prompt_add_file()` 将生成结果追加到 `prompt_result_file.py`。
- `parse_text_tool_call()` 兼容模型把工具调用误输出成 JSON 文本的情况。

建议升级：

- 增加 Prompt 类型：角色类、工作流类、工具调用类、评估类。
- 将生成结果保存为结构化记录：名称、版本、来源关键词、创建时间、正文。
- 增加 Prompt 质量检查：是否包含角色、任务、上下文、输入、输出要求。

## rag_product

定位：独立学习 RAG 知识库能力，为最终 Agent 项目提供设计经验。

当前状态：

- 只有文本切分器和 Chroma 方向的预研注释。

建议升级：

- 先在本项目内实现统一接口，再分别优化短文本、中文本、长文本。
- 增加 ingestion、chunking、embedding、retrieval、answering 五个阶段。
- 记录引用来源，避免回答无法溯源。

详细方案见 [RAG 分层方案](RAG_STRATEGY.md)。

## mcp_product

定位：理解并实现 MCP 服务端和客户端，形成标准化工具调用能力。

已有能力：

- `server.py` 定义 MCP 服务和工具。
- `search_google_news()` 模拟新闻搜索并保存 JSON。
- `analyze_sentiment()` 调用模型生成舆情分析 Markdown。
- `client.py` 通过 stdio 连接 MCP Server。
- `process_query()` 尝试规划工具调用链并保存模型输出。

注意事项：

- `search_google_news()` 当前是模拟数据，还没有真正请求 Serper API。
- `plan_tool_usage()` 当前提示要求 JSON 数组，但代码读取的是 `tool_calls`，这里后续需要统一。
- `send_email_with_attachment` 在客户端逻辑中被引用，但服务端尚未提供该工具。

建议升级：

- 工具规划返回统一 JSON，并做 schema 校验。
- 增加真实工具：搜索、文件读写、报告生成、邮件发送。
- 给每个 MCP 工具补单元测试和异常路径。

## langchain_product

定位：基于 LangChain 实现短期记忆、中期摘要记忆和长期记忆。

已有能力：

- `DatabaseChatMessageHistory` 持久化聊天消息。
- `SummaryChatMessageHistory` 在历史过长时生成摘要。
- `UserMemoryExtractor` 从对话中抽取长期用户事实。
- `DatabaseSessionHistoryStore` 管理窗口、历史和用户记忆。
- `DebugMemoryAssistant` 根据 token 数判断使用短期历史或摘要路线。

建议升级：

- 在本项目内抽象 Memory Service，总结后迁移到 LangGraph 最终项目。
- 长期记忆检索从简单关键词排序升级到向量检索或混合检索。
- 增加敏感信息过滤、用户确认、记忆删除机制。

## langgraph_product

定位：最终上线项目所在地。前面几个目录负责独立学习，`langgraph_product` 负责把成熟思路生成或重写成真正的 Agent 项目。

已有能力：

- `main_graph.py` 演示主图调用子图。
- `sub_graph.py` 演示子图状态转换。
- `main.py` 可显示图并运行示例。

建议升级：

- 定义真实 `AgentState`，包含用户输入、意图、记忆、检索结果、工具结果、最终回答。
- 增加条件路由：是否需要 RAG、是否需要 MCP、是否需要写 Prompt、是否需要人工确认。
- 根据 `langchain_product` 的学习成果设计 Memory 节点。
- 根据 `rag_product`、`mcp_product` 的学习成果设计 RAG 节点和工具节点。
