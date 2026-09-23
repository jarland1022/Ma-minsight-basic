"""Disposition simulation service tests."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.db.enums import DispositionSimulationApprovalStatus
from app.defense_assets.disposition.simulation_service import DispositionSimulationService
from app.models.defense_assets import DispositionSimulation


@pytest.mark.asyncio
async def test_approve_simulation() -> None:
    session = AsyncMock()
    record = DispositionSimulation(
        id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        action_type="block_ip",
        action_params={"ip": "1.2.3.4"},
        simulated_impact={"affected_host_count": 1},
        approval_status=DispositionSimulationApprovalStatus.DRAFT,
    )
    session.get = AsyncMock(return_value=record)
    service = DispositionSimulationService(session)
    updated = await service.approve(record.id, approved_by_id=uuid.uuid4())
    assert updated is not None
    assert updated.approval_status == DispositionSimulationApprovalStatus.APPROVED


@pytest.mark.asyncio
async def test_reject_simulation() -> None:
    session = AsyncMock()
    record = DispositionSimulation(
        id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        action_type="isolate_host",
        action_params={"host_name": "web-01"},
        simulated_impact={},
        approval_status=DispositionSimulationApprovalStatus.DRAFT,
    )
    session.get = AsyncMock(return_value=record)
    service = DispositionSimulationService(session)
    ok = await service.reject(record.id)
    assert ok is True
    assert record.approval_status == DispositionSimulationApprovalStatus.REJECTED
