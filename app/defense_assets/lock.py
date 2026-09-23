"""Distributed lock for defense asset pipeline."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from app.core.redis import get_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def defense_asset_lock(*, ttl_seconds: int = 600) -> AsyncIterator[bool]:
    redis = await get_redis()
    key = "defense_assets:lock:pipeline"
    token = uuid.uuid4().hex
    acquired = await redis.set(key, token, nx=True, ex=ttl_seconds)
    if not acquired:
        logger.info("Defense asset pipeline lock busy")
        yield False
        return
    try:
        yield True
    finally:
        current = await redis.get(key)
        if current == token:
            await redis.delete(key)
