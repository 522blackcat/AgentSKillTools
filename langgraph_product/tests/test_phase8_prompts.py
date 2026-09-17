from __future__ import annotations

from app.builder.project_writer import _render_files
from app.builder.validator import REQUIRED_FILES
from app.prompts.registry import render_prompt


def test_prompt_registry_renders_answer_prompt() -> None:
    prompt = render_prompt(
        "answer",
        memory_context="user prefers concise output",
        rag_context="[1] policy",
        user_input="summarize this",
    )
    assert "user prefers concise output" in prompt
    assert "[1] policy" in prompt
    assert "summarize this" in prompt
    assert "Do not reveal" in prompt


def test_generated_project_contains_prompt_assets() -> None:
    files = _render_files(
        {
            "name": "law_agent",
            "domain": "law_firm",
            "domain_template": {
                "default_prompts": {
                    "system": "Tenant law system prompt.",
                    "review_summary": "Tenant review summary prompt.",
                    "no_answer": "Tenant no-answer prompt.",
                },
                "required_modules": ["human_review", "rag_with_citations"],
            },
            "security": {
                "compliance_profile": {"risk_level": "high"},
                "rbac": ["owner", "admin", "reviewer", "user"],
            },
        }
    )
    assert "docs/ARCHITECTURE.md" in files
    assert "docs/RUNBOOK.md" in files
    assert "app/settings.py" in files
    assert "app/llm/gateway.py" in files
    assert "app/auth/policy.py" in files
    assert "app/observability/events.py" in files
    assert "app/evals/cases.py" in files
    assert "app/prompts/answer.md" in files
    assert "app/prompts/review_summary.md" in files
    assert "app/prompts/domains/policy.md" in files
    assert "app/rag/embedding.py" in files
    assert "app/rag/repository.py" in files
    assert "app/rag/citations.py" in files
    assert "embedding_vector <=>" in files["app/rag/repository.py"]
    assert "ts_rank_cd" in files["app/rag/repository.py"]
    assert "validate_citations" in files["app/rag/citations.py"]
    assert "Tenant law system prompt." in files["app/prompts/answer.md"]
    assert "Tenant review summary prompt." in files["app/prompts/review_summary.md"]
    assert {
        "docs/ARCHITECTURE.md",
        "app/settings.py",
        "app/llm/gateway.py",
        "app/auth/policy.py",
        "app/evals/cases.py",
        "app/rag/embedding.py",
        "app/rag/repository.py",
        "app/rag/citations.py",
        "app/prompts/answer.md",
        "app/prompts/review_summary.md",
    }.issubset(REQUIRED_FILES)
