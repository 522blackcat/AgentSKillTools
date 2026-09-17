"""Build the LangGraph app."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    agent_builder_supervisor,
    answer_with_evidence,
    clarify,
    direct_answer,
    input_guard,
    intent_router,
    load_memory,
    persist_run,
    plan_tools,
    reject,
    retrieve_knowledge,
)
from app.graph.routing import route_after_router
from app.graph.state import AgentState


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("input_guard", input_guard)
    graph.add_node("load_memory", load_memory)
    graph.add_node("intent_router", intent_router)
    graph.add_node("direct_answer", direct_answer)
    graph.add_node("retrieve_knowledge", retrieve_knowledge)
    graph.add_node("answer_with_evidence", answer_with_evidence)
    graph.add_node("plan_tools", plan_tools)
    graph.add_node("agent_builder_supervisor", agent_builder_supervisor)
    graph.add_node("clarify", clarify)
    graph.add_node("reject", reject)
    graph.add_node("persist_run", persist_run)

    graph.add_edge(START, "input_guard")
    graph.add_edge("input_guard", "load_memory")
    graph.add_edge("load_memory", "intent_router")
    graph.add_conditional_edges(
        "intent_router",
        route_after_router,
        {
            "direct": "direct_answer",
            "rag": "retrieve_knowledge",
            "tool": "plan_tools",
            "builder": "agent_builder_supervisor",
            "clarify": "clarify",
            "reject": "reject",
        },
    )
    graph.add_edge("retrieve_knowledge", "answer_with_evidence")
    graph.add_edge("direct_answer", "persist_run")
    graph.add_edge("answer_with_evidence", "persist_run")
    graph.add_edge("plan_tools", "persist_run")
    graph.add_edge("agent_builder_supervisor", "persist_run")
    graph.add_edge("clarify", "persist_run")
    graph.add_edge("reject", "persist_run")
    graph.add_edge("persist_run", END)
    return graph.compile()


agent_graph = build_graph()
