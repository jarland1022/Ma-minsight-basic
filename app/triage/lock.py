"""Redis lock for triage batch runs."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

TRIAGE_LOCK_KEY = "triage:lock:global"
DEFAULT_TTL_SECONDS = 300


@asynccontextmanager
async def triage_lock(*, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> AsyncIterator[bool]:
    redis = await get_redis()
    token = uuid.uuid4().hex
    acquired = await redis.set(TRIAGE_LOCK_KEY, token, nx=True, ex=ttl_seconds)
    if not acquired:
        logger.info("Triage lock busy, skipping run")
        yield False
        return

    try:
        yield True
    finally:
        current = await redis.get(TRIAGE_LOCK_KEY)
        if current == token:
            await redis.delete(TRIAGE_LOCK_KEY)
