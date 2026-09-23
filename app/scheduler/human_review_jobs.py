"""APScheduler jobs for human review dispatch."""

from __future__ import annotations

import logging

from app.db.session import async_session_factory
from app.human_review.audit_sampler import AuditSampleService
from app.human_review.config import ensure_human_review_defaults
from app.human_review.service import HumanReviewService
from app.scheduler.ingestion_jobs import scheduler
from app.services.system_config import get_config_int

logger = logging.getLogger(__name__)

HUMAN_REVIEW_POLL_KEY = "human_review.poll_interval_minutes"
DEFAULT_HUMAN_REVIEW_MINUTES = 2


async def ensure_human_review_scheduler_defaults() -> None:
    async with async_session_factory() as session:
        await ensure_human_review_defaults(session)
        await session.commit()


async def scheduled_human_review_job() -> None:
    async with async_session_factory() as session:
        review_service = HumanReviewService(session)
        audit_service = AuditSampleService(session)
        try:
            review_result = await review_service.run(use_lock=True)
            audit_result = await audit_service.run(limit=20)
            logger.info(
                "Scheduled human review: dispatched=%s expired=%s audit_created=%s lock=%s",
                review_result.dispatched,
                review_result.expired,
                audit_result.created,
                review_result.skipped_lock,
            )
        except Exception:
            logger.exception("Scheduled human review job failed")
            await session.rollback()


async def configure_human_review_scheduler() -> None:
    async with async_session_factory() as session:
        interval = await get_config_int(session, HUMAN_REVIEW_POLL_KEY, DEFAULT_HUMAN_REVIEW_MINUTES)

    scheduler.add_job(
        scheduled_human_review_job,
        trigger="interval",
        minutes=interval,
        id="human_review_poll",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("Human review scheduler configured: every %s minutes", interval)
