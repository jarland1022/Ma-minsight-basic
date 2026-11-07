"""Tests for phase 2 closure evaluator."""

from __future__ import annotations

from app.agent.closure_evaluator import ClosureConfig, ClosureEvaluator
from app.agent.conclusion import ConclusionPayload
from app.db.enums import InvestigationVerdict, RiskLevel
from app.investigation.hypothesis_templates import BRUTE_FORCE_HYPOTHESIS_TEMPLATE


def _conclusion(**overrides: object) -> ConclusionPayload:
    base = {
        "verdict": InvestigationVerdict.LIKELY_FALSE_POSITIVE,
        "confidence": 0.8,
        "risk_level": RiskLevel.LOW,
        "reasoning": "test",
    }
    base.update(overrides)
    return ConclusionPayload.model_validate(base)


def test_closure_passes_with_required_skills() -> None:
    result = ClosureEvaluator.evaluate(
        _conclusion(),
        skills_called={"query_asset", "query_threat_intel", "query_entity_graph"},
        hypothesis_template=BRUTE_FORCE_HYPOTHESIS_TEMPLATE,
        config=ClosureConfig(),
    )
    assert result.passed is True
    assert result.evidence_closure_score >= 0.6


def test_closure_rejects_attack_without_refutation() -> None:
    result = ClosureEvaluator.evaluate(
        _conclusion(verdict=InvestigationVerdict.ATTACK_CONFIRMED, risk_level=RiskLevel.HIGH),
        skills_called={"query_threat_intel", "query_history_alerts"},
        hypothesis_template=BRUTE_FORCE_HYPOTHESIS_TEMPLATE,
        config=ClosureConfig(require_refutation_attempt=True),
    )
    assert result.passed is False
    assert any("反证" in r for r in result.rejection_reasons)


def test_insufficient_information_exempt() -> None:
    result = ClosureEvaluator.evaluate(
        _conclusion(
            verdict=InvestigationVerdict.INSUFFICIENT_INFORMATION,
            human_query="需要确认",
        ),
        skills_called=set(),
        hypothesis_template=BRUTE_FORCE_HYPOTHESIS_TEMPLATE,
        config=ClosureConfig(),
    )
    assert result.passed is True
