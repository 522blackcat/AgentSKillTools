"""Prompt engineering training templates.

These templates are not final prompts. They are learning scaffolds that help
compare different prompt types used by real agents.
"""

from __future__ import annotations


PROMPT_TYPES = {
    "agent": {
        "name": "Agent task prompt",
        "purpose": "用于定义一个可执行任务的 Agent 角色、目标、输入和输出。",
        "sections": ["角色", "任务", "上下文", "工具", "流程", "输入", "输出要求", "失败处理"],
    },
    "router": {
        "name": "Router prompt",
        "purpose": "用于判断用户意图，把请求分发到不同能力或节点。",
        "sections": ["角色", "可选路线", "判断规则", "输入", "输出 JSON", "边界情况"],
    },
    "tool": {
        "name": "Tool-use prompt",
        "purpose": "用于约束模型什么时候调用工具、如何填参数、如何处理工具结果。",
        "sections": ["角色", "可用工具", "工具选择规则", "参数规则", "执行流程", "失败处理"],
    },
    "rag": {
        "name": "RAG answer prompt",
        "purpose": "用于基于检索片段回答问题，并要求引用来源和拒答边界。",
        "sections": ["角色", "知识来源", "回答规则", "引用规则", "输入", "输出要求", "不知道时的处理"],
    },
    "memory": {
        "name": "Memory extraction prompt",
        "purpose": "用于从对话中抽取长期稳定事实、偏好、目标和限制。",
        "sections": ["角色", "抽取范围", "忽略规则", "敏感信息规则", "输入", "输出 JSON"],
    },
    "evaluator": {
        "name": "Prompt evaluator prompt",
        "purpose": "用于评价一个 Prompt 的完整性、清晰度、可执行性和风险。",
        "sections": ["角色", "评分维度", "输入", "输出 JSON", "改进建议"],
    },
}


def format_prompt_types() -> str:
    lines = []
    for prompt_type, item in PROMPT_TYPES.items():
        sections = "、".join(item["sections"])
        lines.append(
            f"- {prompt_type}: {item['name']}。用途：{item['purpose']} 必备部分：{sections}"
        )
    return "\n".join(lines)
