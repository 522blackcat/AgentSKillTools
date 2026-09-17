"""LangGraph runtime for the generated agent.

Routes: direct, rag, tool, builder, clarify, reject
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.human_review.service import requires_review
from app.llm.gateway import complete
from app.rag.service import answer_with_citations


GRAPH_NODES = [
    "input_guard",
    "load_memory",
    "intent_router",
    "retrieve_knowledge",
    "answer",
    "human_review",
    "persist_audit",
]

DEFAULT_REVIEW_REQUIRED = False


class AgentState(TypedDict, total=False):
    tenant_id: str
    knowledge_base_id: str
    user_input: str
    chunks: list[dict]
    memory_context: dict
    risk_level: str
    route: str
    answer: str
    citations: list[str]
    review_required: bool
    audit_nodes: list[str]


def route_intent(user_input: str) -> str:
    text = user_input.lower()
    if "知识库" in text or "cite" in text:
        return "rag"
    if "工具" in text or "execute" in text:
        return "tool"
    return "direct"


def input_guard(state: AgentState) -> dict:
    user_input = state.get("user_input", "").strip()
    if not user_input:
        return {"answer": "请输入有效问题。", "route": "reject"}
    return {"user_input": user_input}


def load_memory(state: AgentState) -> dict:
    return {"memory_context": state.get("memory_context", {})}


def intent_router(state: AgentState) -> dict:
    return {"route": route_intent(state.get("user_input", ""))}


def retrieve_knowledge(state: AgentState) -> dict:
    rag_result = answer_with_citations(
        query=state.get("user_input", ""),
        chunks=state.get("chunks"),
        tenant_id=state.get("tenant_id", ""),
        knowledge_base_id=state.get("knowledge_base_id", ""),
    )
    return {"answer": rag_result["answer"], "citations": rag_result["citations"]}


def answer(state: AgentState) -> dict:
    memory_context = state.get("memory_context", {})
    prompt = state.get("user_input", "")
    if memory_context:
        prompt = f"Memory context:\n{memory_context}\n\nUser input:\n{prompt}"
    response = complete(prompt)
    return {"answer": response["text"], "citations": []}


def human_review(state: AgentState) -> dict:
    risk_level = state.get("risk_level", "low")
    review = DEFAULT_REVIEW_REQUIRED or requires_review(risk_level)
    return {"review_required": review}


def persist_audit(state: AgentState) -> dict:
    return {"audit_nodes": GRAPH_NODES}


def route_after_intent(state: AgentState) -> str:
    if state.get("route") == "rag":
        return "retrieve_knowledge"
    return "answer"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("input_guard", input_guard)
    graph.add_node("load_memory", load_memory)
    graph.add_node("intent_router", intent_router)
    graph.add_node("retrieve_knowledge", retrieve_knowledge)
    graph.add_node("answer", answer)
    graph.add_node("human_review", human_review)
    graph.add_node("persist_audit", persist_audit)

    graph.add_edge(START, "input_guard")
    graph.add_edge("input_guard", "load_memory")
    graph.add_edge("load_memory", "intent_router")
    graph.add_conditional_edges(
        "intent_router",
        route_after_intent,
        {
            "retrieve_knowledge": "retrieve_knowledge",
            "answer": "answer",
        },
    )
    graph.add_edge("retrieve_knowledge", "human_review")
    graph.add_edge("answer", "human_review")
    graph.add_edge("human_review", "persist_audit")
    graph.add_edge("persist_audit", END)
    return graph.compile()


agent_graph = build_graph()


def invoke_graph(
    user_input: str,
    tenant_id: str = "",
    knowledge_base_id: str = "",
    chunks: list[dict] | None = None,
    risk_level: str = "low",
    memory_context: dict | None = None,
) -> dict:
    """执行生成项目的 LangGraph 流程。"""

    return agent_graph.invoke(
        {
            "tenant_id": tenant_id,
            "knowledge_base_id": knowledge_base_id,
            "user_input": user_input,
            "chunks": chunks,
            "risk_level": risk_level,
            "memory_context": memory_context or {},
        }
    )
