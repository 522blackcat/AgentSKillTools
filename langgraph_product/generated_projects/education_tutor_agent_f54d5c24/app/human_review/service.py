"""Human review contract."""

DECISIONS = ['approve', 'reject', 'revise', 'needs_more_info']


def requires_review(risk_level: str) -> bool:
    return risk_level in {"medium", "high"}
