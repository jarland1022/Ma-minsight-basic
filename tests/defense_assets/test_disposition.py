"""Disposition service tests."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.db.enums import DispositionStatus
from app.defense_assets.disposition.service import DispositionService
from app.models.defense_assets import DispositionRecord


@pytest.mark.asyncio
async def test_confirm_disposition() -> None:
    session = AsyncMock()
    record = DispositionRecord(
        id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        suggested_action="建议隔离主机",
        status=DispositionStatus.SUGGESTED,
    )
    session.get = AsyncMock(return_value=record)
    service = DispositionService(session)
    updated = await service.confirm(record.id, confirmed_action="建议隔离主机")
    assert updated is not None
    assert updated.status == DispositionStatus.CONFIRMED


@pytest.mark.asyncio
async def test_reject_disposition() -> None:
    session = AsyncMock()
    record = DispositionRecord(
        id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        suggested_action="建议隔离主机",
        status=DispositionStatus.SUGGESTED,
    )
    session.get = AsyncMock(return_value=record)
    service = DispositionService(session)
    ok = await service.reject(record.id)
    assert ok is True
    assert record.status == DispositionStatus.REJECTED
