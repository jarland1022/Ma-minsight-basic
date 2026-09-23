"""simulate_disposition skill tests."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.context import EventBrief, InvestigationContext
from app.defense_assets.disposition.config import DispositionConfig
from app.defense_assets.disposition.simulator import SimulationResult
from app.skills.simulate_disposition import SimulateDispositionSkill


def _ctx() -> InvestigationContext:
    return InvestigationContext(
        investigation_id=uuid.uuid4(),
        event=EventBrief(
            id=uuid.uuid4(),
            title="test",
            primary_category="brute_force",
            queue_priority=1,
            risk_score=80,
            alert_count=1,
            first_alert_at=None,
            last_alert_at=None,
        ),
        alerts=[],
        model_name="deepseek-chat",
    )


@pytest.mark.asyncio
async def test_skill_disabled() -> None:
    skill = SimulateDispositionSkill()
    session = AsyncMock()
    with patch(
        "app.skills.simulate_disposition.load_disposition_config",
        AsyncMock(return_value=DispositionConfig(simulation_enabled=False)),
    ):
        result = await skill.execute(
            {"action_type": "block_ip", "action_params": {"ip": "1.2.3.4"}},
            _ctx(),
            session,
        )
    assert result.success is False
    assert result.error == "disabled"


@pytest.mark.asyncio
async def test_skill_creates_draft_record() -> None:
    skill = SimulateDispositionSkill()
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    sim_result = SimulationResult(
        action_type="block_ip",
        action_params={"ip": "1.2.3.4"},
        simulated_impact={"affected_host_count": 2, "mode": "mock"},
        summary="[推演/Mock] block_ip",
    )

    with patch(
        "app.skills.simulate_disposition.load_disposition_config",
        AsyncMock(
            return_value=DispositionConfig(
                simulation_enabled=True,
                require_approval=True,
                allowed_action_types=["block_ip"],
            )
        ),
    ), patch(
        "app.skills.simulate_disposition.DispositionSimulator.simulate",
        AsyncMock(return_value=sim_result),
    ):
        result = await skill.execute(
            {"action_type": "block_ip", "action_params": {"ip": "1.2.3.4"}},
            _ctx(),
            session,
        )

    assert result.success is True
    assert result.data["approval_status"] == "draft"
    session.add.assert_called_once()
    assert "draft" in result.summary
