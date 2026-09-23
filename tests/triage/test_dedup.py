"""Dedup handler tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.enums import RouteDecision
from app.models.ingestion import AlertDedupGroup
from app.triage.config import TriageConfig
from app.triage.handlers.dedup import DedupHandler
from app.triage.schemas.context import AlertSnapshot, TriageContext


def _ctx(fingerprint: str = "fp123") -> TriageContext:
    return TriageContext(
        alert=AlertSnapshot(
            id=uuid.uuid4(),
            data_source_id=uuid.uuid4(),
            data_source_name="wazuh",
            source_alert_id="1",
            fingerprint=fingerprint,
            severity=3,
            occurred_at=datetime.now(UTC),
        )
    )


@pytest.mark.asyncio
async def test_dedup_creates_new_group() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()

    ctx = await DedupHandler().handle(_ctx(), session, TriageConfig())
    assert ctx.dedup_hit is False
    assert ctx.is_representative is True
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_dedup_hit_when_representative_exists() -> None:
    now = datetime.now(UTC)
    group = AlertDedupGroup(
        id=uuid.uuid4(),
        fingerprint="fp123",
        first_seen_at=now,
        last_seen_at=now,
        occurrence_count=1,
        representative_alert_id=uuid.uuid4(),
        window_start=now,
        window_end=now + timedelta(minutes=60),
    )
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = group
    session.execute = AsyncMock(return_value=result)

    ctx = await DedupHandler().handle(_ctx(), session, TriageConfig())
    assert ctx.dedup_hit is True
    assert ctx.route_decision == RouteDecision.ARCHIVE_DEDUP
    assert ctx.short_circuit is True


@pytest.mark.asyncio
async def test_dedup_resets_expired_window() -> None:
    now = datetime.now(UTC)
    group = AlertDedupGroup(
        id=uuid.uuid4(),
        fingerprint="fp123",
        first_seen_at=now - timedelta(hours=2),
        last_seen_at=now - timedelta(hours=2),
        occurrence_count=5,
        representative_alert_id=uuid.uuid4(),
        window_start=now - timedelta(hours=2),
        window_end=now - timedelta(minutes=1),
    )
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = group
    session.execute = AsyncMock(return_value=result)

    ctx = await DedupHandler().handle(_ctx(), session, TriageConfig())
    assert ctx.dedup_hit is False
    assert group.representative_alert_id is None
    assert group.occurrence_count == 1
