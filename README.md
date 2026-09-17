# AgentSkillTools

AI Agent 学习与项目生成工作区。

这个仓库不是单一应用。它包含多条 Agent 能力学习线，最终主平台在 `langgraph_product`。

## 当前主目标

构建一个本地 AI Agent 项目生成平台。

用户输入：

```text
生成一个 XX AI Agent 项目
```

平台输出：

```text
一套可运行、可测试、结构完整、方便程序员继续改的 XX AI Agent 工程骨架
```

生成项目不是最终业务系统。  
生成后，程序员继续落地字段、业务逻辑、真实工具、权限、UI 和部署。

## 工作区结构

```text
AgentSkillTools/
├── prompt_product/       # Prompt 工程学习项目
├── rag_product/          # RAG 能力学习项目
├── mcp_product/          # MCP 服务端/客户端学习项目
├── langchain_product/    # LangChain memory 学习项目
├── langgraph_product/    # 当前主平台：AI Agent 项目生成器
├── docs/                 # 工作区级文档
├── requirements.txt      # 根目录依赖
└── README.md             # 当前文件
```

## 子项目说明

| 目录 | 作用 | 当前定位 |
| --- | --- | --- |
| `prompt_product` | Prompt 生成、工具 schema、Prompt 草稿保存 | 学习与参考 |
| `rag_product` | 文档切分、向量库、RAG pipeline | 学习与参考 |
| `mcp_product` | MCP server/client、工具调用协议 | 学习与参考 |
| `langchain_product` | 短期/摘要/长期 memory | 学习与参考 |
| `langgraph_product` | LangGraph 项目生成平台 | 当前主项目 |

## `langgraph_product` 做什么

`langgraph_product` 是当前重点。

它能：

- 提供本地前端页面。
- 接收项目领域、项目名、需求描述。
- 生成 Agent 项目 blueprint。
- 生成 domain profile。
- 写出完整项目文件到 `generated_projects/`。
- 自动运行 compile、pytest、eval。
- 返回生成路径、validation、eval 结果。

生成出来的项目包含：

- FastAPI。
- LangGraph。
- `/v1/agent/invoke`。
- RAG。
- memory。
- tool stub。
- domain CRUD scaffold。
- prompt 文件。
- 标准 Agent 项目目录。
- tests。
- docs。
- pgvector migration 文件。

## 快速运行主平台

进入主平台目录：

```powershell
Set-Location .\langgraph_product
```

启动后端：

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开前端：

```text
http://127.0.0.1:8000/ui/
```

停止后端：

```text
Ctrl + C
```

## 前端怎么用

页面字段：

- **项目领域**：选择预设领域，或选择自定义领域。
- **项目名**：用于生成 blueprint 和生成目录名。
- **需求描述**：描述要生成什么 AI Agent 项目。

点击：

```text
生成并校验
```

页面会显示：

- 文件数。
- validation 状态。
- eval 状态。
- 生成目录。
- domain profile。
- readiness。

生成目录示例：

```text
langgraph_product/generated_projects/ecommerce_support_agent_92f44e55
```

## 项目领域

当前预设：

- `ecommerce`：电商客服。
- `education`：教育培训。
- `real_estate`：房产中介。
- `investment`：投研分析。
- `law_firm`：律所。
- `hospital`：医院。

也支持自定义领域：

```text
fitness_coach
travel_planner
hr_recruiting
```

预设领域生成更稳定。  
自定义领域生成更通用。

## 测试

进入 `langgraph_product`：

```powershell
Set-Location .\langgraph_product
```

运行全部测试：

```powershell
..\.venv\Scripts\python.exe -m pytest
```

运行关键链路测试：

```powershell
..\.venv\Scripts\python.exe -m pytest tests\test_phase16_generic_domain_builder.py tests\test_phase15_generated_law_project.py tests\test_phase5_multi_agent_builder.py
```

## 根目录环境变量

根目录 `.env` 可放模型和外部服务配置。

常见字段：

```env
MODEL_PROVIDER=openai_compatible
MODEL_ID=
BASE_URL=
API_KEY=
TEMPERATURE=0

EMBEDDING_MODEL=
EMBEDDING_BASE_URL=
EMBEDDING_API_KEY=

DATABASE_URL=
REDIS_URL=
SERPER_API_KEY=
```

当前主平台生成项目主链路基本不依赖真实 LLM。  
没有 API key 也能跑 MVP。

## 文档入口

工作区文档：

- [项目蓝图](docs/PROJECT_BLUEPRINT.md)
- [系统架构](docs/ARCHITECTURE.md)
- [学习项目说明](docs/MODULES.md)
- [RAG 分层方案](docs/RAG_STRATEGY.md)
- [开发路线图](docs/ROADMAP.md)
- [运行手册](docs/RUNBOOK.md)
- [决策记录](docs/DECISIONS.md)

主平台文档：

- [langgraph_product README](langgraph_product/README.md)
- [使用说明](langgraph_product/docs/01-usage.md)
- [学习路径](langgraph_product/docs/02-learning-path.md)
- [核心流程](langgraph_product/docs/03-core-flow.md)
- [API 地图](langgraph_product/docs/04-api-map.md)
- [Windows Docker 手册](langgraph_product/docs/05-windows-docker-runbook.md)
- [LLM 与 Graph 配置](langgraph_product/docs/06-llm-and-graph-config.md)

## 注意点

1. `langgraph_product` 是当前主项目。

   其他目录主要是学习、验证、参考实现。

2. `generated_projects/` 是生成结果。

   不要把它当主平台源码改。

3. 生成项目是 scaffold。

   它可运行、可测试，但不是最终业务系统。

4. 前端是本地检验页面。

   不是正式产品 UI。

5. 多次测试会生成很多项目目录。

   需要时可手动清理 `langgraph_product/generated_projects/`。

6. Windows 路径里有中文时，尽量用仓库内 `.venv` 命令。

   示例：

   ```powershell
   ..\.venv\Scripts\python.exe -m pytest
   ```

## 推荐验收

1. 启动后端。
2. 打开 `/ui/`。
3. 选择 `电商客服 ecommerce`。
4. 点击生成。
5. 确认：

   ```text
   validation = passed
   eval = passed
   ```

6. 打开生成目录，看生成项目结构。
7. 跑关键测试。

## 当前阶段结论

当前仓库已具备：

- 多条 Agent 能力学习线。
- 一个可运行本地 AI Agent 项目生成平台。
- 一个简单前端用于本地生成与检验。
- 自动生成、校验、eval 的闭环。

后续增强方向：

- 更聪明的需求理解。
- 更细的动态字段生成。
- 更完整的项目导出。
- 更正式的前端控制台。
