"""APScheduler jobs for Agent investigations."""

from __future__ import annotations

import logging

from app.agent.config import ensure_investigation_defaults
from app.agent.orchestrator import InvestigationOrchestrator
from app.db.session import async_session_factory
from app.scheduler.ingestion_jobs import scheduler
from app.services.system_config import get_config_int

logger = logging.getLogger(__name__)

INVESTIGATION_POLL_KEY = "investigation.poll_interval_minutes"
DEFAULT_INVESTIGATION_MINUTES = 3


async def ensure_investigation_scheduler_defaults() -> None:
    async with async_session_factory() as session:
        await ensure_investigation_defaults(session)
        await session.commit()


async def scheduled_investigation_job() -> None:
    async with async_session_factory() as session:
        orchestrator = InvestigationOrchestrator(session)
        try:
            result = await orchestrator.run(use_lock=True)
            logger.info(
                "Scheduled investigation completed: processed=%s lock=%s budget=%s errors=%s",
                result.processed,
                result.skipped_lock,
                result.skipped_budget,
                len(result.errors),
            )
        except Exception:
            logger.exception("Scheduled investigation job failed")
            await session.rollback()


async def configure_investigation_scheduler() -> None:
    async with async_session_factory() as session:
        interval = await get_config_int(session, INVESTIGATION_POLL_KEY, DEFAULT_INVESTIGATION_MINUTES)

    scheduler.add_job(
        scheduled_investigation_job,
        trigger="interval",
        minutes=interval,
        id="investigation_poll",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("Investigation scheduler configured: every %s minutes", interval)
