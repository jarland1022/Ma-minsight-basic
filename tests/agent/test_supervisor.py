"""Supervisor audit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.agent.conclusion import ConclusionPayload
from app.agent.supervisor import InvestigationSupervisor, SupervisorConfig
from app.db.enums import InvestigationVerdict, RiskLevel


def _conclusion(**kwargs: object) -> ConclusionPayload:
    base = {
        "verdict": InvestigationVerdict.LIKELY_FALSE_POSITIVE,
        "confidence": 0.8,
        "risk_level": RiskLevel.LOW,
        "reasoning": "test",
    }
    base.update(kwargs)
    return ConclusionPayload.model_validate(base)


def _tool_call(name: str, summary: str = "ok") -> MagicMock:
    tc = MagicMock()
    tc.skill_name = name
    tc.success = True
    tc.output_summary = summary
    return tc


def test_supervisor_flags_missing_recommended_skills() -> None:
    result = InvestigationSupervisor.audit(
        _conclusion(),
        [_tool_call("query_asset")],
        config=SupervisorConfig(),
        recommended_skills=["query_asset", "query_entity_graph"],
    )
    assert result.passed is False
    assert "missing_recommended_skills" in str(result.findings.get("issues"))


def test_supervisor_flags_path_drift() -> None:
    calls = [_tool_call(f"extra_skill_{i}") for i in range(5)]
    result = InvestigationSupervisor.audit(
        _conclusion(),
        calls,
        config=SupervisorConfig(max_off_sop_skill_calls=2),
        recommended_skills=["query_asset"],
    )
    assert result.passed is False
    assert any("path_drift" in i for i in result.findings.get("issues", []))


def test_supervisor_allows_core_timeline_skill() -> None:
    result = InvestigationSupervisor.audit(
        _conclusion(),
        [
            _tool_call("query_asset"),
            _tool_call("query_behavior_timeline"),
            _tool_call("query_threat_intel"),
        ],
        config=SupervisorConfig(max_off_sop_skill_calls=0),
        recommended_skills=["query_asset"],
    )
    assert result.passed is True


def test_supervisor_flags_attack_without_multi_path() -> None:
    # Bypass schema guard to assert post-submit supervisor still catches this.
    conclusion = ConclusionPayload.model_construct(
        verdict=InvestigationVerdict.ATTACK_CONFIRMED,
        confidence=0.9,
        risk_level=RiskLevel.HIGH,
        reasoning="bad ip 9.9.9.9",
        evidence_refs=[],
        evidence_strength="single_path",
        disposition_grade=None,
        human_query=None,
        missing_info=[],
        suggested_assets=None,
        hypotheses_evaluated=[],
        refutation_summary=None,
        recommended_action=None,
    )
    result = InvestigationSupervisor.audit(
        conclusion,
        [_tool_call("query_threat_intel", "intel for 9.9.9.9")],
        config=SupervisorConfig(),
        recommended_skills=["query_threat_intel"],
    )
    assert any("multi_path" in i for i in result.findings.get("issues", []))
