# 开发路线图

## Phase 0：文档与边界整理

目标：明确每个独立学习项目的定位，以及最终上线项目只在 `langgraph_product` 中生成。

任务：

- 完成项目总文档。
- 明确五个独立学习项目的定位。
- 记录 RAG 三条路线。
- 统一 `.env` 配置命名方案。

验收：

- 新打开项目时能通过 README 理解整体方向。
- 每个子项目都有明确下一步。

## Phase 1：Prompt Product 最小产品化

目标：把关键词生成 Prompt 从脚本变成可持续迭代的小产品。

任务：

- 定义 PromptRecord 数据结构。
- 保存生成结果时记录 keyword、变量名、创建时间、版本。
- 增加质量检查函数。
- 增加基础测试。

验收：

- 输入关键词后稳定生成 Python 变量赋值格式。
- 结果可追踪、可重复查看、可评分。

## Phase 2：RAG Product MVP

目标：建立短文本和中文本 RAG 的本地闭环。

任务：

- 实现文档加载器。
- 实现短/中/长文本策略选择。
- 接入本地向量库。
- 提供 `ingest()`、`search()`、`answer()`。
- 增加引用来源输出。

验收：

- 能导入 Markdown 文档。
- 能基于文档回答问题。
- 能返回引用 chunk。

## Phase 3：MCP Product 工具链可用化

目标：让 MCP 客户端可以稳定发现工具、规划工具、调用工具。

任务：

- 修复工具规划返回格式。
- 将模拟新闻搜索替换为真实 Serper 请求。
- 增加报告生成工具。
- 删除或实现未注册的邮件工具引用。
- 增加工具调用失败提示。

验收：

- 客户端能完成“搜索新闻 -> 情感分析 -> 保存报告”的链路。
- 工具调用参数错误时有清晰反馈。

## Phase 4：Memory 学习成果迁移

目标：把 `langchain_product` 中学到的记忆系统思路，迁移或重写到 `langgraph_product` 的最终 Agent 中。

任务：

- 在 `langchain_product` 中总结 MemoryService 设计。
- 长期记忆增加检索评分。
- 增加记忆写入前的敏感信息过滤。
- 在 `langgraph_product` 中设计 LangGraph memory node。

验收：

- Agent 可以在运行前读取记忆。
- Agent 可以在运行后写入稳定事实。
- 摘要压缩不会删除原始持久化历史。

## Phase 5：生成 LangGraph 最终 Agent

目标：在 `langgraph_product` 中生成最终上线 Agent 项目，把前面独立学习项目沉淀出的能力按需重写进同一个 Agent 图。

任务：

- 定义 `AgentState`。
- 增加意图识别节点。
- 增加 RAG 节点、MCP 节点、Prompt 节点、Memory 节点。
- 增加错误处理和 fallback 节点。
- 增加运行轨迹日志。

验收：

- 用户输入“帮我根据 xxx 生成 Prompt”时走 Prompt 路线。
- 用户输入知识问题时走 RAG 路线。
- 用户输入工具任务时走 MCP 路线。
- Agent 能利用长期记忆调整回答。

## Phase 6：评估与工程化

目标：从能跑升级到可靠。

任务：

- 增加 pytest。
- 增加 RAG 标准问答集。
- 增加 Prompt 生成质量评估。
- 增加日志和错误分类。
- 编写使用案例。

验收：

- 每个模块至少有核心测试。
- 关键链路有可复现的评估数据。
- 新增功能不会破坏已有链路。
