"""Local prompt quality evaluator for the prompt engineering trainer."""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any


REQUIRED_SECTIONS = {
    "role": ("角色", "你是", "身份"),
    "instruction": ("指令", "任务", "目标"),
    "context": ("上下文", "背景"),
    "input": ("输入", "用户输入"),
    "output": ("输出要求", "输出格式", "返回格式"),
    "example": ("示例", "例子"),
}

ADVANCED_SECTIONS = {
    "tool_rules": ("工具", "调用", "参数"),
    "failure_policy": ("失败", "无法", "不知道", "边界"),
    "constraints": ("限制", "不要", "必须", "禁止"),
    "structured_output": ("JSON", "Markdown", "表格", "字段"),
}


@dataclass(frozen=True)
class PromptEvaluation:
    score: int
    level: str
    passed: bool
    missing_sections: list[str]
    strengths: list[str]
    suggestions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.lower() in text.lower() for keyword in keywords)


def evaluate_prompt(prompt: str) -> PromptEvaluation:
    """Score a generated prompt with deterministic local rules."""
    missing = [
        name
        for name, keywords in REQUIRED_SECTIONS.items()
        if not _contains_any(prompt, keywords)
    ]
    strengths = [
        name
        for name, keywords in ADVANCED_SECTIONS.items()
        if _contains_any(prompt, keywords)
    ]

    score = 40
    score += (len(REQUIRED_SECTIONS) - len(missing)) * 8
    score += len(strengths) * 3
    if re.search(r"```.+```", prompt, flags=re.S):
        score += 5
    if re.search(r"\{.+\}", prompt, flags=re.S) or "JSON" in prompt.upper():
        score += 4
    if len(prompt.strip()) >= 300:
        score += 4
    if len(prompt.strip()) < 120:
        score -= 15
    score = max(0, min(100, score))

    suggestions = []
    if missing:
        suggestions.append("补齐缺失部分：" + "、".join(missing))
    if "failure_policy" not in strengths:
        suggestions.append("增加失败处理规则，例如信息不足时如何追问或拒答。")
    if "tool_rules" not in strengths:
        suggestions.append("如果该 Agent 会使用工具，补充工具选择和参数约束。")
    if "structured_output" not in strengths:
        suggestions.append("明确输出结构，最好给出字段、格式或示例。")
    if not suggestions:
        suggestions.append("结构完整，可以继续用真实任务测试效果。")

    if score >= 85:
        level = "excellent"
    elif score >= 70:
        level = "good"
    elif score >= 55:
        level = "needs_work"
    else:
        level = "weak"

    return PromptEvaluation(
        score=score,
        level=level,
        passed=score >= 70,
        missing_sections=missing,
        strengths=strengths,
        suggestions=suggestions,
    )
