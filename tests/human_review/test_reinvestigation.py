"""Reinvestigation budget skip tests."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.human_review.reinvestigation import consume_skip_budget, mark_reinvestigation


@pytest.mark.asyncio
async def test_mark_and_consume_skip_budget() -> None:
    event_id = uuid.uuid4()
    redis = AsyncMock()
    redis.set = AsyncMock()
    redis.get = AsyncMock(side_effect=["1", None])
    redis.delete = AsyncMock(return_value=1)

    with patch("app.human_review.reinvestigation.get_redis", AsyncMock(return_value=redis)):
        await mark_reinvestigation(event_id)
        assert await consume_skip_budget(event_id) is True
        assert await consume_skip_budget(event_id) is False

    redis.set.assert_awaited_once()
    redis.delete.assert_awaited_once()
