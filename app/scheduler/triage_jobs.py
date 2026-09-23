"""APScheduler jobs for alert triage."""

from __future__ import annotations

import logging

from app.db.session import async_session_factory
from app.scheduler.ingestion_jobs import scheduler
from app.services.system_config import get_config_int
from app.triage.config import ensure_triage_defaults
from app.triage.services.triage_service import TriageService

logger = logging.getLogger(__name__)

TRIAGE_POLL_KEY = "triage.poll_interval_minutes"
DEFAULT_TRIAGE_MINUTES = 2


async def ensure_triage_scheduler_defaults() -> None:
    async with async_session_factory() as session:
        await ensure_triage_defaults(session)
        await session.commit()


async def scheduled_triage_job() -> None:
    async with async_session_factory() as session:
        service = TriageService(session)
        try:
            result = await service.run(use_lock=True)
            logger.info(
                "Scheduled triage completed: processed=%s skipped_lock=%s errors=%s",
                result.processed,
                result.skipped_lock,
                len(result.errors),
            )
        except Exception:
            logger.exception("Scheduled triage job failed")
            await session.rollback()


async def configure_triage_scheduler() -> None:
    async with async_session_factory() as session:
        interval = await get_config_int(session, TRIAGE_POLL_KEY, DEFAULT_TRIAGE_MINUTES)

    scheduler.add_job(
        scheduled_triage_job,
        trigger="interval",
        minutes=interval,
        id="triage_poll",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("Triage scheduler configured: every %s minutes", interval)
