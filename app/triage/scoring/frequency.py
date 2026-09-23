"""Frequency scoring via Redis with DB fallback."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import hours_ago
from app.core.redis import get_redis
from app.models.ingestion import Alert
from app.triage.schemas.context import AlertSnapshot

logger = logging.getLogger(__name__)


def frequency_score_from_count(count: int) -> float:
    return min(100.0, max(0.0, count * 15.0))


async def get_frequency_count(
    session: AsyncSession,
    alert: AlertSnapshot,
    *,
    window_hours: int = 1,
) -> int:
    entity = alert.src_ip or alert.host_name or "unknown"
    redis_key = f"freq:1h:{alert.data_source_name}:{entity}:{alert.rule_id or 'any'}"

    try:
        redis = await get_redis()
        count = await redis.incr(redis_key)
        if count == 1:
            await redis.expire(redis_key, window_hours * 3600)
        return int(count)
    except Exception:
        logger.warning("Redis frequency unavailable, falling back to DB", exc_info=True)

    since = hours_ago(window_hours)
    query = select(func.count()).select_from(Alert).where(Alert.occurred_at >= since)
    if alert.src_ip:
        query = query.where(Alert.src_ip == alert.src_ip)
    elif alert.host_name:
        query = query.where(Alert.host_name == alert.host_name)
    if alert.rule_id:
        query = query.where(Alert.rule_id == alert.rule_id)

    result = await session.execute(query)
    return int(result.scalar_one() or 0)
