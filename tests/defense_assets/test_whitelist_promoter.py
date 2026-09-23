"""Whitelist promoter tests."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.enums import WhitelistCandidateStatus, WhitelistRuleStatus
from app.defense_assets.config import DefenseAssetConfig
from app.defense_assets.whitelist.promoter import WhitelistPromoter
from app.models.triage import WhitelistCandidate


@pytest.mark.asyncio
async def test_confirm_twice_does_not_promote() -> None:
    session = AsyncMock()
    candidate = WhitelistCandidate(
        id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        suggested_pattern={
            "rule_type": "ip",
            "match_pattern": {"field": "src_ip", "op": "eq", "value": "10.0.0.1"},
            "pattern_hash": "abc",
        },
        human_confirmations=0,
        status=WhitelistCandidateStatus.PENDING,
    )
    session.get = AsyncMock(return_value=candidate)
    session.flush = AsyncMock()
    session.add = MagicMock()

    promoter = WhitelistPromoter(session, DefenseAssetConfig(whitelist_promotion_threshold=3))
    rule = await promoter.confirm_candidate(candidate.id)
    assert rule is None
    assert candidate.human_confirmations == 1


@pytest.mark.asyncio
async def test_confirm_third_time_promotes_active() -> None:
    session = AsyncMock()
    candidate = WhitelistCandidate(
        id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        suggested_pattern={
            "rule_type": "ip",
            "match_pattern": {"field": "src_ip", "op": "eq", "value": "10.0.0.1"},
            "pattern_hash": "abc",
        },
        human_confirmations=2,
        status=WhitelistCandidateStatus.PENDING,
    )
    session.get = AsyncMock(return_value=candidate)
    session.flush = AsyncMock()
    session.add = MagicMock()

    promoter = WhitelistPromoter(session, DefenseAssetConfig(whitelist_promotion_threshold=3))
    rule = await promoter.confirm_candidate(candidate.id)
    assert rule is not None
    assert rule.status == WhitelistRuleStatus.ACTIVE
    assert candidate.status == WhitelistCandidateStatus.PROMOTED
