"""Distributed lock for human review jobs."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

DEFAULT_LOCK_TTL_SECONDS = 300


@asynccontextmanager
async def human_review_lock(
    *,
    ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
) -> AsyncIterator[bool]:
    redis = await get_redis()
    key = "human_review:lock:dispatch"
    token = uuid.uuid4().hex
    acquired = await redis.set(key, token, nx=True, ex=ttl_seconds)
    if not acquired:
        logger.info("Human review lock busy")
        yield False
        return

    try:
        yield True
    finally:
        current = await redis.get(key)
        if current == token:
            await redis.delete(key)
