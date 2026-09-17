# prompt_product

这是一个独立的 Prompt 工程训练项目。目标不是只生成一段提示词，而是通过“系统 Prompt + tool calling + 保存 + 评估 + 记录”的闭环，熟悉真实 AI Agent 项目里的 Prompt 工程方法。

## 学习目标

通过这个项目重点掌握：

- 如何写系统 Prompt 控制 Agent 行为。
- 如何把 Python 函数转换为模型可调用工具。
- 如何要求模型在合适时机调用工具。
- 如何设计不同类型的 Agent Prompt。
- 如何对生成的 Prompt 做质量评估。
- 如何记录 Prompt 版本，方便后续复盘和迭代。

## 支持的 Prompt 类型

| 类型 | 训练目标 |
| --- | --- |
| `agent` | 定义一个可执行任务的 Agent 角色、目标、输入和输出 |
| `router` | 判断用户意图，把请求分发到不同能力或节点 |
| `tool` | 约束模型什么时候调用工具、如何填参数、如何处理工具结果 |
| `rag` | 基于检索片段回答问题，并要求引用来源和拒答边界 |
| `memory` | 从对话中抽取长期稳定事实、偏好、目标和限制 |
| `evaluator` | 评价 Prompt 的完整性、清晰度、可执行性和风险 |

## 运行

```bash
python -m prompt_product.llm
```

示例输入：

```text
生成一个 RAG 类型的合同审查 Prompt
```

```text
生成一个 tool 类型的新闻舆情分析 Prompt
```

```text
评估下面这段 Prompt：你是客服助手，请回答用户问题。
```

## 输出文件

- `prompt_result_file.py`：按 Python 变量赋值形式追加保存生成的 Prompt。
- `prompt_records.jsonl`：结构化训练记录，每一行包含生成时间、Prompt 类型、变量名、评分、建议和 Prompt 正文。

## 质量评分

评分由 `evaluator.py` 在本地完成，不依赖大模型。它会检查：

- 是否包含角色、任务目标、上下文、输入、示例、输出要求。
- 是否包含工具规则、失败处理、约束、结构化输出等增强项。
- Prompt 是否过短、是否具备可测试性。

这个评分不是绝对真理，而是训练用的检查清单。真正的 Prompt 质量还需要通过真实任务样例继续验证。

## 推荐训练顺序

1. 先生成 `agent` 类型 Prompt，理解基础结构。
2. 再生成 `tool` 类型 Prompt，理解工具调用约束。
3. 再生成 `rag` 类型 Prompt，理解引用来源和知识边界。
4. 再生成 `memory` 类型 Prompt，理解长期记忆抽取。
5. 最后生成 `router` 和 `evaluator` 类型 Prompt，理解 Agent 图中的路由和评估。
