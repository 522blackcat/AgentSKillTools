from app.agents.supervisor import describe_supervisor
from app.evals.runner import run_evals
from app.reviews.service import review_decision_options, should_pause_for_review
from app.runs.service import create_run, finish_run
from app.database import SessionLocal


def test_standard_agent_project_packages_exist() -> None:
    supervisor = describe_supervisor()
    assert "router" in supervisor["specialist_agents"]
    assert "rag_answerer" in supervisor["specialist_agents"]
    assert review_decision_options()
    assert should_pause_for_review("high") is True
    assert run_evals()["status"] == "passed"


def test_run_service_records_run_lifecycle() -> None:
    with SessionLocal() as db:
        run = create_run(
            db,
            tenant_id="tenant-runs",
            user_id="user-runs",
            graph_name="main",
            input_json={"message": "hello"},
        )
        finished = finish_run(db, run, {"answer": "ok"})
        assert finished.status == "completed"
        assert finished.output_json["answer"] == "ok"
