"""Scoring component tests."""

from app.triage.scoring.category_risk import DEFAULT_CATEGORY_RISK, category_risk_score
from app.triage.scoring.frequency import frequency_score_from_count
from app.triage.scoring.severity import severity_score


def test_severity_score_mapping() -> None:
    assert severity_score(5) == 100.0
    assert severity_score(1) == 20.0


def test_frequency_score_caps_at_100() -> None:
    assert frequency_score_from_count(1) == 15.0
    assert frequency_score_from_count(10) == 100.0


def test_category_risk_defaults() -> None:
    assert category_risk_score("brute_force", DEFAULT_CATEGORY_RISK) == 90.0
    assert category_risk_score("unknown_cat", DEFAULT_CATEGORY_RISK) == 50.0
