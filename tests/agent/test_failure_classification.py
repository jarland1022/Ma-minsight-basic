"""P0-03 / P0-05 failure classification and conclusion protection tests."""

from __future__ import annotations

from app.agent.conclusion import degraded_conclusion, security_incomplete_conclusion
from app.agent.failure import (
    blocks_auto_pick,
    classify_llm_error,
    classify_skill_error,
    is_ops_failure_class,
    rejects_deterministic_verdict,
)
from app.db.enums import InvestigationFailureClass, InvestigationStatus, InvestigationVerdict


def test_classify_llm_missing_key() -> None:
    fc, code = classify_llm_error(RuntimeError("DEEPSEEK_API_KEY is not configured"))
    assert fc == InvestigationFailureClass.LLM_SERVICE.value
    assert code == "llm_not_configured"
    assert is_ops_failure_class(fc)


def test_classify_llm_http_500() -> None:
    fc, code = classify_llm_error(RuntimeError("Server error 500"))
    assert fc == InvestigationFailureClass.LLM_SERVICE.value
    assert code == "llm_http_5xx"


def test_optional_skill_not_ops_class() -> None:
    assert classify_skill_error("timeout talking to foo", required=False) == (
        InvestigationFailureClass.DATASOURCE.value
    )
    # datasource is ops; optional non-datasource is optional_skill
    assert classify_skill_error("validation failed", required=False) == (
        InvestigationFailureClass.OPTIONAL_SKILL.value
    )
    assert not is_ops_failure_class(InvestigationFailureClass.OPTIONAL_SKILL.value)


def test_required_skill_is_ops() -> None:
    fc = classify_skill_error("boom", required=True)
    assert fc == InvestigationFailureClass.REQUIRED_SKILL.value
    assert is_ops_failure_class(fc)


def test_blocks_auto_pick_on_failed() -> None:
    assert blocks_auto_pick(status=InvestigationStatus.FAILED, failure_class=None)
    assert blocks_auto_pick(
        status=InvestigationStatus.DEGRADED,
        failure_class=InvestigationFailureClass.LLM_SERVICE.value,
    )
    assert not blocks_auto_pick(status=InvestigationStatus.COMPLETED, failure_class=None)
    assert not blocks_auto_pick(
        status=InvestigationStatus.NEEDS_HUMAN,
        failure_class=InvestigationFailureClass.SECURITY_EVIDENCE_INSUFFICIENT.value,
    )


def test_rejects_deterministic_when_required_skills_failed() -> None:
    assert rejects_deterministic_verdict(
        InvestigationVerdict.ATTACK_CONFIRMED,
        failed_required_skills={"query_asset"},
    )
    assert not rejects_deterministic_verdict(
        InvestigationVerdict.INSUFFICIENT_INFORMATION,
        failed_required_skills={"query_asset"},
    )
    assert not rejects_deterministic_verdict(
        InvestigationVerdict.ATTACK_CONFIRMED,
        failed_required_skills=set(),
    )


def test_security_incomplete_not_ops_wording() -> None:
    c = security_incomplete_conclusion("证据不足")
    assert c.verdict == InvestigationVerdict.NEEDS_HUMAN_REVIEW
    assert "证据不足" in (c.human_query or "")
    # degraded_conclusion is alias for security path only
    d = degraded_conclusion("same")
    assert d.verdict == InvestigationVerdict.NEEDS_HUMAN_REVIEW
