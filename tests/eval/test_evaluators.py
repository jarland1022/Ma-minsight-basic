"""Evaluator unit tests."""

from app.db.enums import InvestigationVerdict
from app.eval.evaluators.metrics import compute_regression_metrics
from app.eval.evaluators.outcome_diff import diff_outcome
from app.eval.evaluators.verdict_skills import CaseEvalResult, evaluate_case
from app.eval.probe.guard import is_probe_fields


def test_is_probe_fields() -> None:
    assert is_probe_fields({"health_probe": True})
    assert not is_probe_fields({})
    assert not is_probe_fields(None)


def test_evaluate_case_pass() -> None:
    result = evaluate_case(
        case_id="1",
        case_name="test",
        expected_verdict=InvestigationVerdict.LIKELY_FALSE_POSITIVE,
        expected_skills=["query_asset"],
        forbidden_skills=["query_threat_intel"],
        actual_verdict=InvestigationVerdict.LIKELY_FALSE_POSITIVE,
        actual_skills=["query_asset", "query_history_alerts"],
    )
    assert result.passed


def test_evaluate_case_forbidden_skill() -> None:
    result = evaluate_case(
        case_id="1",
        case_name="test",
        expected_verdict=InvestigationVerdict.LIKELY_FALSE_POSITIVE,
        expected_skills=["query_asset"],
        forbidden_skills=["query_threat_intel"],
        actual_verdict=InvestigationVerdict.LIKELY_FALSE_POSITIVE,
        actual_skills=["query_asset", "query_threat_intel"],
    )
    assert not result.passed
    assert not result.forbidden_ok


def test_diff_outcome() -> None:
    passed, mismatches = diff_outcome(
        {"alert_status": "new", "route_decision": "queue_deep_review"},
        {"alert_status": "new", "route_decision": "archive_low_risk"},
    )
    assert not passed
    assert "route_decision" in mismatches


def test_compute_regression_metrics() -> None:
    results = [
        CaseEvalResult(
            case_id="1",
            case_name="a",
            passed=True,
            expected_verdict="likely_false_positive",
            actual_verdict="likely_false_positive",
            expected_skills=["query_asset"],
            actual_skills=["query_asset"],
            forbidden_skills=[],
            verdict_match=True,
            skills_ok=True,
            forbidden_ok=True,
        ),
        CaseEvalResult(
            case_id="2",
            case_name="b",
            passed=False,
            expected_verdict="attack_confirmed",
            actual_verdict="likely_false_positive",
            expected_skills=[],
            actual_skills=[],
            forbidden_skills=[],
            verdict_match=False,
            skills_ok=True,
            forbidden_ok=True,
        ),
    ]
    metrics = compute_regression_metrics(results)
    assert metrics["total"] == 2
    assert metrics["passed"] == 1
    assert metrics["failed"] == 1
    assert metrics["accuracy"] == 0.5
