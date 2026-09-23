"""Redis lock for investigation runs."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

INVESTIGATE_LOCK_KEY = "investigate:lock:global"
DEFAULT_TTL_SECONDS = 600


@asynccontextmanager
async def investigate_lock(*, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> AsyncIterator[bool]:
    redis = await get_redis()
    token = uuid.uuid4().hex
    acquired = await redis.set(INVESTIGATE_LOCK_KEY, token, nx=True, ex=ttl_seconds)
    if not acquired:
        logger.info("Investigation lock busy")
        yield False
        return
    try:
        yield True
    finally:
        current = await redis.get(INVESTIGATE_LOCK_KEY)
        if current == token:
            await redis.delete(INVESTIGATE_LOCK_KEY)
