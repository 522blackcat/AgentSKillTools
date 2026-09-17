# 运行手册

## 环境准备

```bash
pip install -r requirements.txt
```

创建根目录 `.env`：

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

## Prompt 生成

```bash
python -m prompt_product.llm
```

输入关键词，例如：

```text
法律合同审查
```

预期结果：

- 模型生成完整 Prompt。
- 调用 `write_prompt_add_file`。
- 结果追加到 `prompt_product/prompt_result_file.py`。

## MCP 客户端

```bash
python -m mcp_product.client
```

启动后客户端会通过 stdio 启动 `mcp_product/server.py`，并列出服务端工具。

当前可用工具：

- `search_google_news`
- `analyze_sentiment`

注意：

- 新闻搜索当前返回模拟数据。
- 舆情分析依赖 `.env` 中的模型配置。
- 客户端里的邮件附件逻辑还未接入服务端工具。

## Memory 调试

```bash
python -m langchain_product.memory.debug_runner
```

运行过程：

1. 输入 `user_id`。
2. 输入或新建 `session_id`。
3. 多轮对话。
4. 控制台会输出当前使用短期记忆还是摘要记忆。

数据默认写入：

```text
chat_memory.db
```

## LangGraph 示例

```bash
python -m langgraph_product.graph.main
```

当前图逻辑：

```text
number=5
sub_step1: 5 * 2 = 10
sub_step2: 10 + 10 = 20
final_result=20
```

如果本地没有 Graphviz 或 PyGraphviz 环境，图展示可能失败，但图执行逻辑仍可单独测试。

## 常见问题

### 模型配置不统一

当前 `prompt_product` 和 `mcp_product` 使用 `LLM_*`，`langgraph_product` 使用 `API_KEY` / `MODEL_ID` 等。后续建议统一配置模块。

### MCP 工具规划失败

`plan_tool_usage()` 当前要求模型返回 JSON 数组，但代码尝试读取 `tool_calls`。建议下一步修正为解析 `message.content` 中的 JSON，或者改成真正的工具调用规划。

### RAG 还不能运行

`rag_product` 目前是设计占位。先按 `docs/RAG_STRATEGY.md` 实现 MVP。
