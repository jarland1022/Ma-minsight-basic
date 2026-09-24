"""Conclusion schema tests."""

import pytest

from app.agent.conclusion import ConclusionPayload, degraded_conclusion, parse_conclusion
from app.db.enums import InvestigationVerdict, RiskLevel


def test_parse_valid_conclusion() -> None:
    payload = parse_conclusion(
        {
            "verdict": "attack_confirmed",
            "confidence": 0.9,
            "risk_level": "high",
            "reasoning": "Timeline + threat intel both point to C2.",
            "evidence_refs": ["timeline:host:pc-1", "intel:ip:1.2.3.4"],
            "evidence_strength": "multi_path",
        }
    )
    assert payload.verdict == InvestigationVerdict.ATTACK_CONFIRMED
    assert payload.evidence_strength == "multi_path"
    assert payload.disposition_grade == "confirmed_compromise"


def test_attack_confirmed_requires_multi_path() -> None:
    with pytest.raises(Exception):
        parse_conclusion(
            {
                "verdict": "attack_confirmed",
                "confidence": 0.9,
                "risk_level": "high",
                "reasoning": "Only one intel hit",
                "evidence_strength": "single_path",
            }
        )


def test_insufficient_requires_human_query() -> None:
    with pytest.raises(Exception):
        parse_conclusion(
            {
                "verdict": "insufficient_information",
                "confidence": 0.3,
                "risk_level": "medium",
                "reasoning": "Need operator input",
            }
        )


def test_insufficient_with_human_query() -> None:
    payload = parse_conclusion(
        {
            "verdict": "insufficient_information",
            "confidence": 0.3,
            "risk_level": "medium",
            "reasoning": "Need operator input",
            "human_query": "请确认该账号是否在出差期间登录？",
        }
    )
    assert payload.human_query is not None


def test_degraded_conclusion() -> None:
    c = degraded_conclusion("test failure")
    assert c.verdict == InvestigationVerdict.NEEDS_HUMAN_REVIEW
