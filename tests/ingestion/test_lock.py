"""Tests for Redis ingest distributed lock."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ingestion.lock import ingest_lock


@pytest.mark.asyncio
async def test_lock_acquired_and_released() -> None:
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value="token-value")
    redis.delete = AsyncMock(return_value=1)

    with patch("app.ingestion.lock.get_redis", AsyncMock(return_value=redis)):
        token = MagicMock()
        token.hex = "token-value"
        with patch("app.ingestion.lock.uuid.uuid4", return_value=token):
            async with ingest_lock("source-1") as acquired:
                assert acquired is True

    redis.set.assert_awaited_once()
    redis.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_lock_not_acquired_when_busy() -> None:
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=None)

    with patch("app.ingestion.lock.get_redis", AsyncMock(return_value=redis)):
        async with ingest_lock("source-1") as acquired:
            assert acquired is False

    redis.delete.assert_not_called()
