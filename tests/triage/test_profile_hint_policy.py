"""Profile hint must not cause archive."""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime

import pytest

from app.db.enums import RouteDecision
from app.triage.config import TriageConfig
from app.triage.handlers.router import RouteHandler
from app.triage.schemas.context import AlertSnapshot, TriageContext


@pytest.mark.asyncio
async def test_high_profile_hint_low_score_still_archives_low_risk() -> None:
    ctx = TriageContext(
        alert=AlertSnapshot(
            id=uuid.uuid4(),
            data_source_id=uuid.uuid4(),
            data_source_name="wazuh",
            source_alert_id="1",
            fingerprint="fp",
            severity=1,
            occurred_at=datetime.now(UTC),
        ),
        profile_hint_score=20.0,
        rule_score=10.0,
        effective_score=10.0,
    )
    handler = RouteHandler(rng=random.Random(1))
    result = await handler.handle(ctx, None, TriageConfig(sample_audit_rate=0.0))
    assert result.route_decision == RouteDecision.ARCHIVE_LOW_RISK
    assert result.whitelist_rule_id is None
