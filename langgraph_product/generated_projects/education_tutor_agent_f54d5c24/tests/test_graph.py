from app import settings
from app.graph import GRAPH_NODES, agent_graph, invoke_graph, route_intent


def test_route_rag() -> None:
    assert route_intent("根据知识库回答") == "rag"


def test_graph_exposes_production_nodes() -> None:
    assert "human_review" in GRAPH_NODES
    assert "persist_audit" in GRAPH_NODES
    assert agent_graph is not None


def test_graph_invokes_llm_boundary() -> None:
    settings.MODEL_PROVIDER = "stub"
    settings.MODEL_ID = "stub-chat"
    settings.API_KEY = ""
    result = invoke_graph("hello")
    assert result["route"] == "direct"
    assert result["answer"]


def test_domain_marker() -> None:
    assert "education"
