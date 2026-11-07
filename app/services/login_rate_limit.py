"""Redis-backed login failure rate limiting (P0-01)."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status

from app.core.config import settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


def _key(ip: str | None, username: str) -> str:
    return f"minsight:login:fail:{ip or 'unknown'}:{username.strip().lower()}"


async def assert_login_allowed(ip: str | None, username: str) -> None:
    try:
        redis = await get_redis()
        raw = await redis.get(_key(ip, username))
        if raw is not None and int(raw) >= settings.login_rate_limit_max:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts; try again later",
            )
    except HTTPException:
        raise
    except Exception:
        logger.warning("login rate-limit check failed; allowing attempt", exc_info=True)


async def record_login_failure(ip: str | None, username: str) -> None:
    try:
        redis = await get_redis()
        key = _key(ip, username)
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, settings.login_rate_limit_window_seconds)
    except Exception:
        logger.warning("login rate-limit record failed", exc_info=True)


async def clear_login_failures(ip: str | None, username: str) -> None:
    try:
        redis = await get_redis()
        await redis.delete(_key(ip, username))
    except Exception:
        logger.warning("login rate-limit clear failed", exc_info=True)
