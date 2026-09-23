"""Distributed lock for ingestion jobs."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

DEFAULT_LOCK_TTL_SECONDS = 600


@asynccontextmanager
async def ingest_lock(
    data_source_id: str,
    *,
    ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
) -> AsyncIterator[bool]:
    """Acquire Redis lock for a data source ingest run.

    Yields True if lock acquired, False if another worker holds it.
    """
    redis = await get_redis()
    key = f"ingest:lock:{data_source_id}"
    token = uuid.uuid4().hex
    acquired = await redis.set(key, token, nx=True, ex=ttl_seconds)
    if not acquired:
        logger.info("Ingest lock busy for data_source=%s", data_source_id)
        yield False
        return

    try:
        yield True
    finally:
        current = await redis.get(key)
        if current == token:
            await redis.delete(key)
