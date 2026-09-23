"""Aggregation merge target selection tests."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.enums import EventStatus
from app.models.investigation import Event
from app.aggregation.services.aggregation_service import AggregationService


@pytest.mark.asyncio
async def test_find_merge_target_returns_pending_event() -> None:
    service = AggregationService(AsyncMock())
    pending = Event(
        id=uuid.uuid4(),
        event_key="abc",
        status=EventStatus.PENDING_REVIEW,
        risk_score=0.0,
        alert_count=0,
        queue_priority=0,
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = pending
    service.session.execute = AsyncMock(return_value=result)

    found = await service._find_merge_target("abc")
    assert found is pending


@pytest.mark.asyncio
async def test_no_pending_event_means_create_new() -> None:
    service = AggregationService(AsyncMock())
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    service.session.execute = AsyncMock(return_value=result)

    found = await service._find_merge_target("abc")
    assert found is None
