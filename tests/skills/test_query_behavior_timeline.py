"""query_behavior_timeline skill tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.context import AlertBrief, EventBrief, InvestigationContext
from app.skills.query_behavior_timeline import QueryBehaviorTimelineSkill


def _ctx(*, host: str | None = "pc-finance-01", src_ip: str = "10.20.3.15") -> InvestigationContext:
    now = datetime.now(UTC)
    return InvestigationContext(
        investigation_id=uuid.uuid4(),
        event=EventBrief(
            id=uuid.uuid4(),
            title="C2 beacon",
            primary_category="malware",
            queue_priority=1,
            risk_score=90,
            alert_count=2,
            first_alert_at=now - timedelta(minutes=5),
            last_alert_at=now,
            aggregate_host_name=host,
        ),
        alerts=[
            AlertBrief(
                id=uuid.uuid4(),
                occurred_at=now,
                rule_name="Malware C2 Beacon Outbound",
                severity=12,
                src_ip=src_ip,
                host_name=host,
            )
        ],
    )


def _alert(
    *,
    occurred_at: datetime,
    rule_name: str,
    src_ip: str = "10.20.3.15",
    dst_ip: str | None = "45.227.252.147",
    dst_port: int | None = 443,
    host_name: str = "pc-finance-01",
    category: str = "malware",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        source_alert_id=f"wazuh-{uuid.uuid4().hex[:8]}",
        occurred_at=occurred_at,
        rule_name=rule_name,
        severity=10,
        alert_category=category,
        src_ip=src_ip,
        dst_ip=dst_ip,
        dst_port=dst_port,
        user_name=None,
        host_name=host_name,
        process_name=None,
        file_hash=None,
    )


@pytest.mark.asyncio
async def test_timeline_builds_sourced_rows() -> None:
    skill = QueryBehaviorTimelineSkill()
    ctx = _ctx()
    now = ctx.event.last_alert_at
    a1 = _alert(occurred_at=now - timedelta(minutes=4), rule_name="DNS query update-sync.top", category="dns")
    a2 = _alert(occurred_at=now, rule_name="Malware C2 Beacon Outbound", category="malware")

    session = MagicMock()

    async def _execute(stmt):  # noqa: ANN001
        result = MagicMock()
        # First call: event alerts; second: entity window
        if not hasattr(_execute, "n"):
            _execute.n = 0
        _execute.n += 1
        if _execute.n == 1:
            result.scalars.return_value.all.return_value = [a2]
        else:
            result.scalars.return_value.all.return_value = [a1, a2]
        return result

    session.execute = AsyncMock(side_effect=_execute)

    out = await skill.execute({}, ctx, session)
    assert out.success
    assert out.data["total"] == 2
    assert out.data["timeline"][0]["source_ref"].startswith("alert:")
    assert "verification" in out.data
    assert out.evidence_ref.startswith("timeline:")


@pytest.mark.asyncio
async def test_timeline_defaults_entity_from_event_host() -> None:
    skill = QueryBehaviorTimelineSkill()
    entity_type, entity_key = skill._resolve_entity({}, _ctx(host="host-a"))
    assert entity_type == "host"
    assert entity_key == "host-a"
