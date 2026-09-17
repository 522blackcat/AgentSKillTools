from app.human_review.service import requires_review


def test_high_risk_requires_review() -> None:
    assert requires_review("high") is True
