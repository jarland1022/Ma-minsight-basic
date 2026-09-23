"""Reinvestigation budget skip marker in Redis."""

from __future__ import annotations

from uuid import UUID

from app.core.redis import get_redis

_SKIP_BUDGET_TTL = 86400


def _skip_budget_key(event_id: UUID) -> str:
    return f"investigate:skip_budget:{event_id}"


async def mark_reinvestigation(event_id: UUID) -> None:
    redis = await get_redis()
    await redis.set(_skip_budget_key(event_id), "1", ex=_SKIP_BUDGET_TTL)


async def consume_skip_budget(event_id: UUID) -> bool:
    redis = await get_redis()
    key = _skip_budget_key(event_id)
    if await redis.get(key):
        await redis.delete(key)
        return True
    return False
