"""Tests for frequency DB fallback datetime handling."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.datetime_utils import as_naive_utc
from app.triage.schemas.context import AlertSnapshot
from app.triage.scoring.frequency import get_frequency_count


@pytest.mark.asyncio
async def test_frequency_db_fallback_uses_naive_datetime() -> None:
    alert = AlertSnapshot(
        alert_id=uuid4(),
        data_source_name="wazuh",
        occurred_at=as_naive_utc(datetime.now(UTC)),
        src_ip="203.0.113.1",
        rule_id="5710",
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=AsyncMock(scalar_one=AsyncMock(return_value=3)))

    with patch("app.triage.scoring.frequency.get_redis", AsyncMock(side_effect=RuntimeError("down"))):
        count = await get_frequency_count(session, alert, window_hours=1)

    assert count == 3
    stmt = session.execute.await_args.args[0]
    since_param = stmt.compile().params
    for value in since_param.values():
        if isinstance(value, datetime):
            assert value.tzinfo is None
