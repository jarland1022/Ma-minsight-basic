"""Daily investigation event budget via Redis."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.redis import get_redis


def _daily_key() -> str:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"investigate:daily_count:{today}"


async def get_daily_count() -> int:
    redis = await get_redis()
    raw = await redis.get(_daily_key())
    return int(raw or 0)


async def increment_daily_count() -> int:
    redis = await get_redis()
    key = _daily_key()
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 86400 * 2)
    return int(count)


async def budget_remaining(daily_budget: int) -> int:
    return max(0, daily_budget - await get_daily_count())
