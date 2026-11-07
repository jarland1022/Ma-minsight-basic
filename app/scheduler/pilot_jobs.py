"""Periodic expiry of time-boxed pilot accounts."""

from __future__ import annotations

import logging

from app.db.session import async_session_factory
from app.scheduler.ingestion_jobs import scheduler
from app.services.audit import write_audit
from app.services.pilot_accounts import expire_due_pilots

logger = logging.getLogger(__name__)


async def scheduled_expire_pilots_job() -> None:
    async with async_session_factory() as session:
        n = await expire_due_pilots(session)
        if n:
            await write_audit(
                session,
                action="user.expire_pilots_scheduled",
                detail={"revoked_count": n},
                commit=True,
            )
            logger.info("Expired %s pilot account(s)", n)
        else:
            await session.commit()


async def configure_pilot_expire_scheduler() -> None:
    scheduler.add_job(
        scheduled_expire_pilots_job,
        trigger="interval",
        hours=1,
        id="pilot_expire",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("Pilot expiry scheduler configured: every 1 hour")
