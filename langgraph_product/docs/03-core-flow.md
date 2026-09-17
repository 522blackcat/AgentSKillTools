# 03 核心生成链路

## 1. 用户创建 builder run

入口：`POST /v1/builder/runs`

这一步只记录“用户想生成什么 Agent”，还没有真正生成代码。

## 2. runtime 执行 run

入口：`app/runtime.py`

runtime 会加载：

- 用户输入
- memory context
- RAG context
- domain template
- model 配置
- token budget

然后调用 LangGraph。

## 3. LangGraph 路由到 builder

入口：`app/graph/nodes.py`

当意图是“生成生产级 Agent 项目”时，会进入 `agent_builder_supervisor`。

## 4. Multi-Agent Builder 生成 blueprint

入口：`app/builder/service.py`

blueprint 是生成项目的中间结构，包含：

- agents
- graph
- database
- memory
- RAG
- human review
- security
- observability
- generated project plan
- validation / eval

## 5. 人工审核

律所、医院等高风险模板会触发审核。

审核通过后才写出项目文件。

## 6. 写出项目并验证

入口：

- `app/builder/project_writer.py`
- `app/builder/validator.py`
- `app/builder/evals.py`

生成项目会写入 `generated_projects/{project_id}`。

