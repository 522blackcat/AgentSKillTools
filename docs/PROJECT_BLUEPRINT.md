# 项目蓝图

## 愿景

构建一个从学习走向生产实践的个人 AI Agent 项目集合。每个子目录都是独立学习项目，文件夹名就是学习主题。前面的项目用于理解和验证 Prompt、RAG、MCP、Memory 等能力，最终上线项目在 `langgraph_product` 中生成。

## 学习路线地图

```text
用户需求
  │
  ├─ prompt_product
  │    └─ 把关键词或任务想法转成结构化 Prompt 草稿
  │
  ├─ rag_product
  │    └─ 按文本长度和业务场景提供知识检索能力
  │
  ├─ mcp_product
  │    └─ 把外部工具封装成标准协议能力
  │
  ├─ langchain_product
  │    └─ 管理短期上下文、中期摘要、长期用户记忆
  │
  └─ langgraph_product
       └─ 生成最终上线的 Agent 项目
```

## 生产级目标

一个生产级 Agent 项目至少需要回答这些问题：

| 维度 | 需要理解的生产级能力 | 学习项目 |
| --- | --- | --- |
| Prompt | 可复用模板、变量填充、版本管理、效果评估 | `prompt_product` |
| Knowledge | 文档导入、切分、索引、检索、重排、引用溯源 | `rag_product` |
| Tools | 工具注册、协议调用、参数校验、失败重试 | `mcp_product` |
| Memory | 会话历史、摘要压缩、长期事实、跨会话召回 | `langchain_product` |
| Workflow | 状态图、条件路由、子图复用、人工确认 | `langgraph_product` |
| Ops | 配置、日志、测试、错误处理、数据隔离 | 全项目 |

## 最终项目形态

`langgraph_product` 是最终上线项目所在地。其他目录不强制作为运行时依赖，而是把已经学明白的设计经验、接口思想和关键代码迁移或重写进最终项目。

```text
langgraph_product/
  agent/
    state.py
    graph.py
    nodes.py
    router.py
  adapters/
    prompt_adapter.py
    rag_adapter.py
    mcp_adapter.py
    memory_adapter.py
  evals/
  tests/
```

核心运行链路：

1. 接收用户输入。
2. 识别任务意图：普通问答、Prompt 生成、知识问答、工具任务、记忆任务。
3. 从 Memory 获取用户偏好和历史上下文。
4. 必要时调用 RAG 检索知识。
5. 必要时通过 MCP 调用外部工具。
6. 由 LangGraph 控制节点流转、失败重试和最终回答。
7. 将稳定事实写入长期记忆，将过程日志写入运行记录。

## 边界

当前阶段先做“独立学习项目 + LangGraph 最终项目雏形”，不急着做多租户、权限系统、分布式部署。优先把每个学习主题吃透，再把成熟设计放进 `langgraph_product`。
