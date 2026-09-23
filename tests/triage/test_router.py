"""Router decision tests."""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime

import pytest

from app.db.enums import RouteDecision
from app.triage.config import TriageConfig
from app.triage.handlers.router import RouteHandler
from app.triage.schemas.context import AlertSnapshot, TriageContext


def _ctx(score: float) -> TriageContext:
    alert = AlertSnapshot(
        id=uuid.uuid4(),
        data_source_id=uuid.uuid4(),
        data_source_name="wazuh",
        source_alert_id="1",
        fingerprint="fp",
        severity=3,
        occurred_at=datetime.now(UTC),
    )
    return TriageContext(alert=alert, effective_score=score, rule_score=score)


@pytest.mark.asyncio
async def test_router_deep_review() -> None:
    handler = RouteHandler()
    ctx = await handler.handle(_ctx(85), None, TriageConfig())
    assert ctx.route_decision == RouteDecision.QUEUE_DEEP_REVIEW


@pytest.mark.asyncio
async def test_router_uncertain_band() -> None:
    handler = RouteHandler()
    ctx = await handler.handle(_ctx(50), None, TriageConfig())
    assert ctx.route_decision == RouteDecision.QUEUE_UNCERTAIN


@pytest.mark.asyncio
async def test_router_low_risk_archive() -> None:
    handler = RouteHandler(rng=random.Random(0))
    config = TriageConfig(sample_audit_rate=0.0)
    ctx = await handler.handle(_ctx(10), None, config)
    assert ctx.route_decision == RouteDecision.ARCHIVE_LOW_RISK


@pytest.mark.asyncio
async def test_router_sample_audit_with_seed() -> None:
    handler = RouteHandler(rng=random.Random(0))
    config = TriageConfig(sample_audit_rate=1.0)
    ctx = await handler.handle(_ctx(10), None, config)
    assert ctx.route_decision == RouteDecision.SAMPLE_AUDIT


@pytest.mark.asyncio
async def test_router_preserves_dedup_short_circuit() -> None:
    handler = RouteHandler()
    ctx = _ctx(0)
    ctx.short_circuit = True
    ctx.route_decision = RouteDecision.ARCHIVE_DEDUP
    result = await handler.handle(ctx, None, TriageConfig())
    assert result.route_decision == RouteDecision.ARCHIVE_DEDUP
