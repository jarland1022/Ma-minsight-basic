"""APScheduler jobs for defense asset sedimentation."""

from __future__ import annotations

import logging

from app.db.session import async_session_factory
from app.defense_assets.config import ensure_defense_asset_defaults
from app.defense_assets.pipeline import AssetPipeline
from app.scheduler.ingestion_jobs import scheduler
from app.services.system_config import get_config_int

logger = logging.getLogger(__name__)

DEFENSE_ASSET_POLL_KEY = "defense_assets.poll_interval_minutes"
DEFAULT_DEFENSE_ASSET_MINUTES = 5


async def ensure_defense_asset_scheduler_defaults() -> None:
    async with async_session_factory() as session:
        await ensure_defense_asset_defaults(session)
        await session.commit()


async def scheduled_defense_asset_job() -> None:
    async with async_session_factory() as session:
        pipeline = AssetPipeline(session)
        try:
            result = await pipeline.run(use_lock=True)
            logger.info(
                "Scheduled defense asset pipeline: processed=%s lock=%s disabled=%s errors=%s",
                result.processed,
                result.skipped_lock,
                result.skipped_disabled,
                len(result.errors),
            )
        except Exception:
            logger.exception("Scheduled defense asset job failed")
            await session.rollback()


async def configure_defense_asset_scheduler() -> None:
    async with async_session_factory() as session:
        interval = await get_config_int(session, DEFENSE_ASSET_POLL_KEY, DEFAULT_DEFENSE_ASSET_MINUTES)

    scheduler.add_job(
        scheduled_defense_asset_job,
        trigger="interval",
        minutes=interval,
        id="defense_assets_poll",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("Defense asset scheduler configured: every %s minutes", interval)
