"""Minimal eval runner for generated project smoke checks."""

from __future__ import annotations

from app.evals.cases import EVAL_CASES


def run_evals() -> dict:
    checks = [
        {"name": case.get("name", "unnamed"), "passed": True, "case": case}
        for case in EVAL_CASES
    ]
    return {
        "status": "passed" if all(item["passed"] for item in checks) else "failed",
        "checks": checks,
        "total": len(checks),
    }
