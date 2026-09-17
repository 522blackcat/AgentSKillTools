"""Graph routing rules."""

from __future__ import annotations

from app.graph.state import AgentState


def route_after_router(state: AgentState) -> str:
    return state.get("route", "direct")


def classify_route(text: str) -> tuple[str, str, str]:
    normalized = text.strip().lower()
    if not normalized:
        return "clarify", "unknown", "low"
    builder_keywords = ["生成", "构建", "build", "agent", "律所", "医院", "生产级"]
    if any(keyword in normalized for keyword in builder_keywords):
        risk = "high" if ("律所" in normalized or "医院" in normalized) else "medium"
        return "builder", "agent_builder", risk
    rag_keywords = ["文档", "知识库", "引用", "资料", "根据"]
    if any(keyword in normalized for keyword in rag_keywords):
        return "rag", "knowledge_qa", "low"
    tool_keywords = ["运行", "执行", "调用", "写入", "删除"]
    if any(keyword in normalized for keyword in tool_keywords):
        return "tool", "tool_use", "medium"
    return "direct", "chat", "low"
