"""APScheduler jobs for alert ingestion."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.db.session import async_session_factory
from app.ingestion.services.ingest_service import IngestService
from app.services.system_config import ensure_config_key, get_config_int

logger = logging.getLogger(__name__)

POLL_INTERVAL_KEY = "ingestion.poll_interval_minutes"
DEFAULT_POLL_MINUTES = 5

scheduler = AsyncIOScheduler()


async def ensure_ingestion_defaults(session: AsyncSession) -> None:
    await ensure_config_key(
        session,
        POLL_INTERVAL_KEY,
        {"value": DEFAULT_POLL_MINUTES},
        description="Interval in minutes between scheduled ingestion polls",
    )
    await session.commit()


async def scheduled_ingest_job() -> None:
    async with async_session_factory() as session:
        service = IngestService(session)
        try:
            results = await service.run_all_active(
                max_batches=settings.ingestion_max_batches_per_run,
            )
            inserted = sum(r.total_inserted for r in results)
            skipped_lock = sum(1 for r in results if r.skipped_lock)
            fetched = sum(sum(b.fetched for b in r.batches) for r in results)
            logger.info(
                "Scheduled ingest completed: sources=%s inserted=%s fetched=%s skipped_lock=%s",
                len(results),
                inserted,
                fetched,
                skipped_lock,
            )
        except Exception:
            logger.exception("Scheduled ingest job failed")
            await session.rollback()


async def configure_scheduler_from_db() -> None:
    async with async_session_factory() as session:
        await ensure_ingestion_defaults(session)
        interval = await get_config_int(session, POLL_INTERVAL_KEY, DEFAULT_POLL_MINUTES)

    scheduler.add_job(
        scheduled_ingest_job,
        trigger="interval",
        minutes=interval,
        id="ingestion_poll",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=utc_now(),
    )
    logger.info("Ingestion scheduler configured: every %s minutes", interval)


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.start()


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
