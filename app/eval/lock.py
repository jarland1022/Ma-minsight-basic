"""Redis locks for eval jobs."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from app.core.redis import get_redis

REGRESSION_LOCK_KEY = "eval:lock:regression"
HEALTH_CHECK_LOCK_KEY = "eval:lock:health_check"
LOCK_TTL_SECONDS = 900


@asynccontextmanager
async def regression_lock() -> AsyncIterator[bool]:
    redis = await get_redis()
    acquired = await redis.set(REGRESSION_LOCK_KEY, "1", nx=True, ex=LOCK_TTL_SECONDS)
    try:
        yield bool(acquired)
    finally:
        if acquired:
            await redis.delete(REGRESSION_LOCK_KEY)


@asynccontextmanager
async def health_check_lock() -> AsyncIterator[bool]:
    redis = await get_redis()
    acquired = await redis.set(HEALTH_CHECK_LOCK_KEY, "1", nx=True, ex=LOCK_TTL_SECONDS)
    try:
        yield bool(acquired)
    finally:
        if acquired:
            await redis.delete(HEALTH_CHECK_LOCK_KEY)
