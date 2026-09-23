"""Aggregation lock tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.aggregation.lock import aggregation_lock


@pytest.mark.asyncio
async def test_aggregation_lock_release() -> None:
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value="token-value")
    redis.delete = AsyncMock(return_value=1)

    with patch("app.aggregation.lock.get_redis", AsyncMock(return_value=redis)):
        token = MagicMock()
        token.hex = "token-value"
        with patch("app.aggregation.lock.uuid.uuid4", return_value=token):
            async with aggregation_lock() as acquired:
                assert acquired is True

    redis.delete.assert_awaited_once()
