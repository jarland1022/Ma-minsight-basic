"""Scheduled regression and health-check jobs."""

from __future__ import annotations

import logging

from apscheduler.triggers.cron import CronTrigger

from app.db.session import async_session_factory
from app.eval.config import ensure_eval_defaults, load_eval_config
from app.eval.health_check.runner import HealthCheckRunner
from app.eval.regression.runner import RegressionRunner
from app.scheduler.ingestion_jobs import scheduler

logger = logging.getLogger(__name__)


async def ensure_eval_scheduler_defaults() -> None:
    async with async_session_factory() as session:
        await ensure_eval_defaults(session)
        await session.commit()


async def scheduled_regression_job() -> None:
    async with async_session_factory() as session:
        config = await load_eval_config(session)
        if not config.regression_enabled:
            return
        try:
            result = await RegressionRunner(session).run(trigger="scheduler", use_lock=True)
            logger.info(
                "Scheduled regression: passed=%s failed=%s",
                result.passed,
                result.failed,
            )
        except Exception:
            logger.exception("Scheduled regression job failed")
            await session.rollback()


async def scheduled_health_check_job() -> None:
    async with async_session_factory() as session:
        config = await load_eval_config(session)
        if not config.health_check_enabled:
            return
        try:
            result = await HealthCheckRunner(session).run(trigger="scheduler", use_lock=True)
            logger.info(
                "Scheduled health check: passed=%s failed=%s",
                result.passed,
                result.failed,
            )
        except Exception:
            logger.exception("Scheduled health check job failed")
            await session.rollback()


async def configure_eval_scheduler() -> None:
    async with async_session_factory() as session:
        config = await load_eval_config(session)

    if config.regression_cron:
        scheduler.add_job(
            scheduled_regression_job,
            trigger=CronTrigger.from_crontab(config.regression_cron),
            id="eval_regression",
            replace_existing=True,
            max_instances=1,
        )
        logger.info("Regression cron configured: %s", config.regression_cron)
    else:
        if scheduler.get_job("eval_regression"):
            scheduler.remove_job("eval_regression")

    if config.health_check_cron:
        scheduler.add_job(
            scheduled_health_check_job,
            trigger=CronTrigger.from_crontab(config.health_check_cron),
            id="eval_health_check",
            replace_existing=True,
            max_instances=1,
        )
        logger.info("Health check cron configured: %s", config.health_check_cron)
    else:
        if scheduler.get_job("eval_health_check"):
            scheduler.remove_job("eval_health_check")
