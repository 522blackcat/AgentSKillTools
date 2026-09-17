"""Human review workflow service.

Generated project starts with review boundaries. Add product-specific approval
screens or policies here.
"""

from __future__ import annotations

from app.human_review.service import requires_review


def review_decision_options() -> list[str]:
    return ["approve", "reject", "revise", "needs_more_info"]


def should_pause_for_review(risk_level: str, action: str = "") -> bool:
    high_risk_action = action in {"external_send", "database_write", "tool_execute"}
    return high_risk_action or requires_review(risk_level)
