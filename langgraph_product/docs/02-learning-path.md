# 02 学习路线

建议不要按文件名硬读，而是按业务链路读。

## 第一阶段：看懂它要解决什么问题

读：

- `README.md`
- `docs/03-core-flow.md`

先记住一句话：

> 这个平台把用户需求转换成生产级 AI Agent 项目。

## 第二阶段：看懂一次 run 怎么执行

读：

- `app/main.py`
- `app/runtime.py`
- `app/graph/state.py`
- `app/graph/nodes.py`

重点看：run 如何进入 graph，graph 如何路由到 builder。

## 第三阶段：看懂项目如何生成

读：

- `app/builder/service.py`
- `app/builder/project_writer.py`
- `app/builder/validator.py`
- `app/builder/evals.py`

重点看：blueprint 如何变成真实文件，如何验证。

## 第四阶段：看懂生产边界

读：

- `app/auth.py`
- `app/model_gateway/gateway.py`
- `app/memory/service.py`
- `app/knowledge/service.py`
- `app/domain_templates.py`
- `app/prompts/registry.py`

