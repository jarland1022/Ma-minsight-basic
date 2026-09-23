"""Human review lock tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.human_review.lock import human_review_lock


@pytest.mark.asyncio
async def test_human_review_lock_acquire_and_release() -> None:
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value="token-value")
    redis.delete = AsyncMock(return_value=1)

    with patch("app.human_review.lock.get_redis", AsyncMock(return_value=redis)):
        token = MagicMock()
        token.hex = "token-value"
        with patch("app.human_review.lock.uuid.uuid4", return_value=token):
            async with human_review_lock() as acquired:
                assert acquired is True

    redis.delete.assert_awaited_once()
