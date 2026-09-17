# LangGraph Product Agent Platform

这是一个本地 AI Agent 项目生成平台。

它的目标不是只做一个聊天机器人，而是让用户输入“生成一个 XX AI Agent 项目”，平台自动生成一套可运行、可测试、结构完整、方便程序员继续二次开发的 AI Agent 工程骨架。

## 这个项目做什么

主平台负责：

- 接收用户的项目需求。
- 生成 Agent 项目 blueprint。
- 根据领域生成 domain profile。
- 写出完整项目文件到 `generated_projects/`。
- 自动运行 compile、pytest、eval。
- 保存生成项目版本、校验结果和 eval 结果。
- 提供简单前端页面用于本地检验。

生成出来的项目会包含：

- FastAPI API 入口。
- LangGraph agent graph。
- `/v1/agent/invoke` 调用接口。
- RAG 知识库、文档入库、上传、混合检索、引用。
- 三层 memory：短期消息、会话 summary、长期 user memory。
- domain CRUD scaffold。
- tool stub registry。
- human review scaffold。
- 标准目录：`agents`、`tools`、`prompts`、`rag`、`memory`、`runs`、`reviews`、`evals`。
- pytest 测试。
- README、架构文档、运行文档。
- pgvector migration 文件。

## 当前定位

这是 **MVP 级项目生成器**。

它生成的是可运行工程骨架，不是最终业务系统。  
生成后，程序员继续改字段、业务逻辑、权限、真实工具连接、UI、部署配置。

## 核心流程

```text
用户输入需求
  -> 创建 builder run
  -> LangGraph 执行
  -> Builder 生成 blueprint
  -> 生成 domain_profile
  -> 写出 generated_project
  -> compile / pytest / eval
  -> 返回生成路径和校验结果
```

高风险领域可能进入人工审核流程。普通领域会直接生成项目。

## 快速启动

在 `langgraph_product` 目录下运行：

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开前端：

```text
http://127.0.0.1:8000/ui/
```

前端可以选择项目领域、填写项目名和需求，然后生成项目。

## 前端怎么用

页面字段：

- **项目领域**：选择预设领域，或选择自定义领域。
- **项目名**：生成项目的名称，也会体现在生成目录名里。
- **需求描述**：描述这个 AI Agent 项目要做什么。

点击 **生成并校验** 后，页面会显示：

- 文件数。
- validation 状态。
- eval 状态。
- 生成目录。
- domain profile。
- readiness。

生成目录示例：

```text
generated_projects/ecommerce_support_agent_92f44e55
```

目录名格式：

```text
{项目名安全化}_{project_id前8位}
```

## 项目领域说明

前端预设领域：

- `ecommerce`：电商客服。
- `education`：教育培训。
- `real_estate`：房产中介。
- `investment`：投研分析。
- `law_firm`：律所。
- `hospital`：医院。

预设领域会生成更稳定的实体、工作流和工具 stub。

也可以选“自定义领域”，例如：

```text
fitness_coach
travel_planner
hr_recruiting
```

自定义领域会走通用 fallback。平台会根据领域 key、项目名和需求描述生成通用实体。

## 后端 API 常用入口

创建 builder run：

```http
POST /v1/builder/runs
```

执行 builder run：

```http
POST /v1/builder/runs/{run_id}/invoke?tenant_id={tenant_id}
```

查看 run：

```http
GET /v1/chat/runs/{run_id}?tenant_id={tenant_id}
```

查看生成项目版本：

```http
GET /v1/generated-projects/{project_id}/versions?tenant_id={tenant_id}
```

查看 validation：

```http
GET /v1/generated-projects/{project_id}/validations?tenant_id={tenant_id}
```

查看 eval report：

```http
GET /v1/generated-projects/{project_id}/eval-reports?tenant_id={tenant_id}
```

修复生成项目：

```http
POST /v1/generated-projects/{project_id}/repair?tenant_id={tenant_id}
```

## 运行测试

运行全部测试：

```powershell
..\.venv\Scripts\python.exe -m pytest
```

运行关键生成链路测试：

```powershell
..\.venv\Scripts\python.exe -m pytest tests\test_phase16_generic_domain_builder.py tests\test_phase15_generated_law_project.py tests\test_phase5_multi_agent_builder.py
```

## 是否需要真实 LLM

当前生成项目主链路基本不依赖真实 LLM。

生成逻辑主要是：

- 规则识别。
- preset。
- blueprint。
- 模板渲染。

如果配置 OpenAI-compatible 模型，部分 chat/model gateway 可以调用真实模型。

`.env` 示例：

```env
MODEL_PROVIDER=openai_compatible
MODEL_ID=your-model
BASE_URL=https://your-compatible-endpoint/v1
API_KEY=your-key
```

不配置也能跑通生成器 MVP。

## 关键代码位置

- `frontend/index.html`：本地前端页面。
- `app/main.py`：FastAPI API 入口。
- `app/runtime.py`：run 执行编排。
- `app/graph/nodes.py`：主平台 LangGraph 节点。
- `app/builder/service.py`：builder，生成 blueprint 和 domain profile。
- `app/builder/project_writer.py`：把 blueprint 写成生成项目文件。
- `app/builder/validator.py`：生成项目校验。
- `app/builder/evals.py`：生成项目 eval。
- `app/domain_templates.py`：内置高风险领域模板。
- `app/prompts/`：主平台 prompt 文件。

## 生成项目会放在哪里

默认路径：

```text
langgraph_product/generated_projects/
```

生成目录由项目名和短 ID 组成。

不要手动把 `generated_projects/` 当成主平台源码改。  
那里是平台输出结果。

## 注意点

1. **这是生成器，不是最终业务系统**

   生成项目是 scaffold。程序员后续继续改业务字段、真实工具、UI、权限和部署。

2. **领域 key 影响生成结果**

   预设领域更稳定。自定义领域也能生成，但更通用。

3. **生成项目默认本地 SQLite**

   生产使用 PostgreSQL + pgvector 时，需要继续完善迁移和部署配置。

4. **生成项目工具是 stub**

   `app/tools/registry.py` 只生成工具契约和 stub executor。真实外部系统连接由程序员后续实现。

5. **高风险领域可能需要审核**

   `law_firm`、`hospital` 等高风险领域可能进入 review 流程。

6. **测试可能生成很多项目目录**

   多次运行测试或前端生成，会在 `generated_projects/` 下产生多个目录。

7. **前端只用于本地检验**

   当前前端是简单静态页面，不是正式产品 UI。

## 推荐本地验收步骤

1. 启动后端。

   ```powershell
   ..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

2. 打开：

   ```text
   http://127.0.0.1:8000/ui/
   ```

3. 选择 `电商客服 ecommerce`。

4. 点击 **生成并校验**。

5. 确认页面显示：

   ```text
   validation = passed
   eval = passed
   ```

6. 打开生成目录，查看生成项目。

7. 如需回归测试，运行：

   ```powershell
   ..\.venv\Scripts\python.exe -m pytest
   ```
