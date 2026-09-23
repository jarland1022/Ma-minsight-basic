"""Disposition simulator unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.defense_assets.disposition.simulator import DispositionSimulator
from app.entity.graph import EntityGraphResult, GraphNode


@pytest.mark.asyncio
async def test_simulate_block_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_graph(*args, **kwargs):
        return EntityGraphResult(
            nodes=[
                GraphNode(entity_type="ip", entity_key="1.2.3.4"),
                GraphNode(entity_type="host", entity_key="web-01", metadata={"business_systems": ["采购系统"]}),
            ],
            edges=[],
            summary="test graph",
        )

    monkeypatch.setattr(
        "app.defense_assets.disposition.simulator.traverse_entity_graph",
        _fake_graph,
    )

    session = AsyncMock()
    profile_result = MagicMock()
    profile_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=profile_result)

    result = await DispositionSimulator().simulate(
        session,
        action_type="block_ip",
        action_params={"ip": "1.2.3.4"},
        mock_mode=True,
    )
    assert result.action_type == "block_ip"
    assert result.simulated_impact["affected_host_count"] >= 1
    assert "采购系统" in result.simulated_impact["business_systems"]
    assert "Mock" in result.summary or "mock" in result.summary.lower()


@pytest.mark.asyncio
async def test_simulate_requires_target() -> None:
    session = AsyncMock()
    with pytest.raises(ValueError, match="ip"):
        await DispositionSimulator().simulate(
            session,
            action_type="block_ip",
            action_params={},
        )
