"""Defense asset lock tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.defense_assets.lock import defense_asset_lock


@pytest.mark.asyncio
async def test_defense_asset_lock() -> None:
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value="token-value")
    redis.delete = AsyncMock(return_value=1)

    with patch("app.defense_assets.lock.get_redis", AsyncMock(return_value=redis)):
        token = MagicMock()
        token.hex = "token-value"
        with patch("app.defense_assets.lock.uuid.uuid4", return_value=token):
            async with defense_asset_lock() as acquired:
                assert acquired is True

    redis.delete.assert_awaited_once()
