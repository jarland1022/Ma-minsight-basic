"""Independent dimension helpers for investigation status vs security verdict (P0-04).

See docs/review/STATUS_VERDICT_SEMANTICS.md.
"""

from __future__ import annotations

from typing import Any

from app.db.enums import InvestigationVerdict, RiskLevel


def compute_evidence_strength(
    *,
    evidence_refs: list[Any] | None,
    evidence_closure_score: float | None = None,
) -> str:
    """Evidence quality — never derived from verdict alone."""
    refs = evidence_refs or []
    n = len(refs)
    score = float(evidence_closure_score) if evidence_closure_score is not None else 0.0
    if n >= 2 and score >= 0.6:
        return "multi_path"
    if n >= 1:
        return "single_path"
    return "none"


def compute_disposition_grade(
    *,
    verdict: InvestigationVerdict,
    risk_level: RiskLevel,
) -> str:
    """Analyst response-priority hint (not a security verdict rewrite).

    Documented mapping:
    - inconclusive / needs review → needs_more_evidence
    - likely FP → false_positive (even if risk_level is HIGH)
    - attack_confirmed + high/critical → confirmed_compromise
    - attack_confirmed + medium/low → suspicious
    """
    if verdict in {
        InvestigationVerdict.INSUFFICIENT_INFORMATION,
        InvestigationVerdict.NEEDS_HUMAN_REVIEW,
    }:
        return "needs_more_evidence"
    if verdict == InvestigationVerdict.LIKELY_FALSE_POSITIVE:
        return "false_positive"
    if verdict == InvestigationVerdict.ATTACK_CONFIRMED:
        if risk_level in {RiskLevel.CRITICAL, RiskLevel.HIGH}:
            return "confirmed_compromise"
        return "suspicious"
    return "needs_more_evidence"


def active_security_verdict(
    *,
    investigation_status: str | None,
    verdict: str | None,
    invalidated_as_ops_failure: bool = False,
    is_ops_failure: bool = False,
) -> str | None:
    """Return verdict only when it is a live security conclusion."""
    if invalidated_as_ops_failure or is_ops_failure:
        return None
    if investigation_status == "failed":
        # Ops FAILED must not advertise a security verdict even if a stale row exists.
        return None
    return verdict
