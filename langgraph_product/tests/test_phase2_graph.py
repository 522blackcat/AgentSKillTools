from __future__ import annotations

from app.graph.builder import agent_graph
from app.graph.routing import classify_route


def test_classify_builder_route() -> None:
    route, intent, risk = classify_route("生成一个生产级律所 AI Agent")
    assert route == "builder"
    assert intent == "agent_builder"
    assert risk == "high"


def test_graph_generates_builder_blueprint() -> None:
    result = agent_graph.invoke(
        {
            "tenant_id": "tenant",
            "user_id": "user",
            "run_id": "run",
            "user_input": "生成一个生产级医院 AI Agent",
            "trace": [],
        }
    )
    assert result["route"] == "builder"
    assert result["agent_blueprint"]["domain"] == "hospital"
    assert result["review_required"] is True
    assert result["final_answer"]
