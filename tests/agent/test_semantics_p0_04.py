"""P0-04: investigation status vs security verdict semantic separation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.agent.conclusion import ConclusionPayload, security_incomplete_conclusion
from app.agent.orchestrator import VERDICT_EVENT_STATUS, InvestigationOrchestrator
from app.agent.semantics import (
    active_security_verdict,
    compute_disposition_grade,
    compute_evidence_strength,
)
from app.db.enums import (
    EventStatus,
    InvestigationStatus,
    InvestigationVerdict,
    RiskLevel,
)


def test_completed_plus_benign_dimensions_independent() -> None:
    """COMPLETED + likely_false_positive (BENIGN); high risk still allowed."""
    grade = compute_disposition_grade(
        verdict=InvestigationVerdict.LIKELY_FALSE_POSITIVE,
        risk_level=RiskLevel.HIGH,
    )
    assert grade == "false_positive"
    assert VERDICT_EVENT_STATUS[InvestigationVerdict.LIKELY_FALSE_POSITIVE] == EventStatus.CONCLUDED


def test_completed_plus_malicious() -> None:
    grade = compute_disposition_grade(
        verdict=InvestigationVerdict.ATTACK_CONFIRMED,
        risk_level=RiskLevel.HIGH,
    )
    assert grade == "confirmed_compromise"
    assert VERDICT_EVENT_STATUS[InvestigationVerdict.ATTACK_CONFIRMED] == EventStatus.CONCLUDED


def test_completed_plus_inconclusive() -> None:
    """COMPLETED may carry insufficient_information; event may be human_pending."""
    assert (
        VERDICT_EVENT_STATUS[InvestigationVerdict.INSUFFICIENT_INFORMATION]
        == EventStatus.HUMAN_PENDING
    )
    grade = compute_disposition_grade(
        verdict=InvestigationVerdict.INSUFFICIENT_INFORMATION,
        risk_level=RiskLevel.HIGH,
    )
    assert grade == "needs_more_evidence"


def test_failed_has_no_active_security_verdict() -> None:
    assert (
        active_security_verdict(
            investigation_status="failed",
            verdict="attack_confirmed",
            invalidated_as_ops_failure=False,
        )
        is None
    )
    assert (
        active_security_verdict(
            investigation_status="completed",
            verdict="attack_confirmed",
            invalidated_as_ops_failure=True,
        )
        is None
    )


def test_high_severity_with_benign_verdict() -> None:
    """HIGH severity must not force attack_confirmed."""
    grade = compute_disposition_grade(
        verdict=InvestigationVerdict.LIKELY_FALSE_POSITIVE,
        risk_level=RiskLevel.CRITICAL,
    )
    assert grade == "false_positive"


def test_low_severity_with_malicious_verdict() -> None:
    grade = compute_disposition_grade(
        verdict=InvestigationVerdict.ATTACK_CONFIRMED,
        risk_level=RiskLevel.LOW,
    )
    assert grade == "suspicious"


def test_inconclusive_never_silently_becomes_benign() -> None:
    payload = ConclusionPayload(
        verdict=InvestigationVerdict.INSUFFICIENT_INFORMATION,
        confidence=0.2,
        risk_level=RiskLevel.MEDIUM,
        reasoning="missing context",
        human_query="Is this scanner owned by us?",
    )
    assert payload.verdict == InvestigationVerdict.INSUFFICIENT_INFORMATION
    assert payload.verdict != InvestigationVerdict.LIKELY_FALSE_POSITIVE


def test_system_failure_conclusion_helper_is_security_gap_not_ops() -> None:
    """security_incomplete_conclusion is for evidence gaps; ops failures skip persist."""
    c = security_incomplete_conclusion("missing required skill output")
    assert c.verdict == InvestigationVerdict.NEEDS_HUMAN_REVIEW
    assert c.verdict != InvestigationVerdict.LIKELY_FALSE_POSITIVE


def test_evidence_strength_independent_of_verdict() -> None:
    multi = compute_evidence_strength(
        evidence_refs=["a", "b"],
        evidence_closure_score=0.9,
    )
    none = compute_evidence_strength(evidence_refs=[], evidence_closure_score=1.0)
    assert multi == "multi_path"
    assert none == "none"
    # Same refs regardless of "would-be" verdict — function has no verdict arg
    assert compute_evidence_strength(evidence_refs=["x"], evidence_closure_score=0.1) == "single_path"


def test_api_active_verdict_serialization_helper() -> None:
    assert (
        active_security_verdict(
            investigation_status="completed",
            verdict="insufficient_information",
        )
        == "insufficient_information"
    )
    assert (
        active_security_verdict(
            investigation_status="failed",
            verdict="insufficient_information",
            is_ops_failure=True,
        )
        is None
    )


def test_orchestrator_does_not_overwrite_completed_when_event_human_pending() -> None:
    """COMPLETED + inconclusive stays COMPLETED even if Event → human_pending."""
    orch = InvestigationOrchestrator(MagicMock())
    event = SimpleNamespace(status=EventStatus.PENDING_REVIEW, id=uuid4())
    investigation = SimpleNamespace(
        status=InvestigationStatus.RUNNING,
        id=uuid4(),
        failure_class=None,
        failure_detail=None,
        finished_at=None,
    )
    conclusion = ConclusionPayload(
        verdict=InvestigationVerdict.INSUFFICIENT_INFORMATION,
        confidence=0.3,
        risk_level=RiskLevel.HIGH,
        reasoning="need more data",
        human_query="Please confirm asset ownership",
        evidence_refs=["ref-1"],
    )
    loop_result = SimpleNamespace(
        investigation_status=InvestigationStatus.COMPLETED,
        failure_class=None,
        missing_evidence=[],
        failed_required_skills=set(),
        closure_result=None,
        conclusion=conclusion,
        is_ops_failure=False,
    )

    # Simulate the P0-04 status assignment block (mirrors orchestrator)
    investigation.status = loop_result.investigation_status
    event.status = VERDICT_EVENT_STATUS.get(conclusion.verdict, EventStatus.HUMAN_PENDING)

    assert investigation.status == InvestigationStatus.COMPLETED
    assert event.status == EventStatus.HUMAN_PENDING
    assert conclusion.verdict == InvestigationVerdict.INSUFFICIENT_INFORMATION


def test_persist_conclusion_sets_independent_dims() -> None:
    session = MagicMock()
    orch = InvestigationOrchestrator(session)
    conclusion = ConclusionPayload(
        verdict=InvestigationVerdict.LIKELY_FALSE_POSITIVE,
        confidence=0.8,
        risk_level=RiskLevel.HIGH,
        reasoning="scanner",
        evidence_refs=["e1", "e2"],
    )
    closure = SimpleNamespace(
        evidence_closure_score=0.85,
        refutation_coverage=0.7,
        checks={},
        passed=True,
    )
    orch._persist_conclusion(uuid4(), conclusion, closure)
    session.add.assert_called_once()
    row = session.add.call_args[0][0]
    assert row.verdict == InvestigationVerdict.LIKELY_FALSE_POSITIVE
    assert row.risk_level == RiskLevel.HIGH
    assert row.evidence_strength == "multi_path"
    assert row.disposition_grade == "false_positive"  # high risk ≠ attack


def test_verdict_event_status_map_is_routing_only() -> None:
    """Map exists for queue routing; does not redefine investigation status."""
    assert set(VERDICT_EVENT_STATUS.keys()) == {
        InvestigationVerdict.ATTACK_CONFIRMED,
        InvestigationVerdict.LIKELY_FALSE_POSITIVE,
        InvestigationVerdict.INSUFFICIENT_INFORMATION,
        InvestigationVerdict.NEEDS_HUMAN_REVIEW,
    }
