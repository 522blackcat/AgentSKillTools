# mcp_product

这是一个独立的 MCP 学习项目，用来理解 MCP 服务端、客户端、stdio 连接和工具调用链。

## 重要区分

Codex 输入 `/MCP` 看到的是 Codex/ChatGPT App 自己已经启用的 MCP 工具，不是本目录的 `mcp_product/server.py`。

本项目的 MCP 服务端是本地 Python 代码，需要通过客户端启动：

```bash
python -m mcp_product.client
```

连接成功后，控制台应该看到类似输出：

```text
已连接到服务器，支持以下工具： ['search_google_news', 'analyze_sentiment']
```

## 配置

根目录 `.env` 需要包含：

```env
LLM_API_KEY="ollama"
LLM_MODEL_ID="qwen3:4b"
LLM_BASE_URL="http://localhost:11434/v1"
SERPER_API_KEY="..."
```

## 诊断

如果 MCP 没启动，先运行：

```bash
python -m mcp_product.diagnose
```

重点检查：

- `.env` 是否加载。
- `mcp` 是否能 import。
- `mcp.server.mcpserver` 是否能 import。
- Windows 下 `pywintypes` 是否能 import。

## 已修正的问题

- 客户端启动服务端时不再写死 `python`，而是使用 `sys.executable`。这样你用哪个 Python 运行客户端，服务端就用同一个 Python，依赖环境会一致。
- Windows MCP stdio 需要 `pywin32`，已写入 `requirements.txt`。
