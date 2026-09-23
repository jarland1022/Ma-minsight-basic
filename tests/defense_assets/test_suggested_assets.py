"""Suggested assets parser tests."""

from __future__ import annotations

import uuid

import pytest

from app.db.enums import InvestigationVerdict, RiskLevel
from app.defense_assets.builders.suggested_assets import extract_match_pattern, pattern_hash
from app.defense_assets.config import DefenseAssetConfig
from app.defense_assets.builders import suggested_assets as sa_module
from app.models.investigation import InvestigationConclusion


def test_pattern_hash_stable() -> None:
    pattern = {"field": "src_ip", "op": "eq", "value": "10.0.0.1"}
    assert pattern_hash(pattern) == pattern_hash(pattern)


def test_extract_nested_match_pattern() -> None:
    wl = {"rule_type": "ip", "match_pattern": {"field": "src_ip", "op": "eq", "value": "1.2.3.4"}}
    match_pattern = extract_match_pattern(wl)
    assert match_pattern is not None
    assert match_pattern["field"] == "src_ip"


def test_extract_flat_condition() -> None:
    match_pattern = extract_match_pattern({"field": "user_name", "op": "eq", "value": "admin"})
    assert match_pattern is not None


@pytest.mark.asyncio
async def test_create_whitelist_skips_non_fp() -> None:
    from unittest.mock import AsyncMock

    config = DefenseAssetConfig(create_whitelist_on_fp_only=True)
    conclusion = InvestigationConclusion(
        investigation_id=uuid.uuid4(),
        verdict=InvestigationVerdict.ATTACK_CONFIRMED,
        confidence=0.9,
        risk_level=RiskLevel.HIGH,
        reasoning="attack",
        suggested_assets={
            "whitelist_candidate": {
                "match_pattern": {"field": "src_ip", "op": "eq", "value": "1.2.3.4"},
            }
        },
    )
    session = AsyncMock()
    result = await sa_module.create_whitelist_candidate_if_applicable(
        session=session,
        investigation_id=conclusion.investigation_id,
        conclusion=conclusion,
        config=config,
    )
    assert result is None
