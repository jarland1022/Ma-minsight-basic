"""APScheduler jobs for event aggregation."""

from __future__ import annotations

import logging

from app.aggregation.config import ensure_aggregation_defaults
from app.aggregation.services.aggregation_service import AggregationService
from app.db.session import async_session_factory
from app.scheduler.ingestion_jobs import scheduler
from app.services.system_config import get_config_int

logger = logging.getLogger(__name__)

AGGREGATION_POLL_KEY = "event.aggregation_poll_interval_minutes"
DEFAULT_AGGREGATION_MINUTES = 2


async def ensure_aggregation_scheduler_defaults() -> None:
    async with async_session_factory() as session:
        await ensure_aggregation_defaults(session)
        await session.commit()


async def scheduled_aggregation_job() -> None:
    async with async_session_factory() as session:
        service = AggregationService(session)
        try:
            result = await service.run(use_lock=True)
            logger.info(
                "Scheduled aggregation completed: processed=%s created=%s merged=%s skipped_lock=%s",
                result.processed,
                result.events_created,
                result.events_merged,
                result.skipped_lock,
            )
        except Exception:
            logger.exception("Scheduled aggregation job failed")
            await session.rollback()


async def configure_aggregation_scheduler() -> None:
    async with async_session_factory() as session:
        interval = await get_config_int(session, AGGREGATION_POLL_KEY, DEFAULT_AGGREGATION_MINUTES)

    scheduler.add_job(
        scheduled_aggregation_job,
        trigger="interval",
        minutes=interval,
        id="aggregation_poll",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("Aggregation scheduler configured: every %s minutes", interval)
