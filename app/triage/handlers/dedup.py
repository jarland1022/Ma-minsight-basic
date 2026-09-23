"""Dedup handler — 60-minute sliding window per fingerprint."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now

from app.db.enums import RouteDecision
from app.models.ingestion import AlertDedupGroup
from app.triage.config import TriageConfig
from app.triage.handlers.base import TriageHandler
from app.triage.schemas.context import TriageContext


class DedupHandler(TriageHandler):
    name = "dedup"

    async def handle(
        self,
        ctx: TriageContext,
        session: AsyncSession,
        config: TriageConfig,
    ) -> TriageContext:
        now = utc_now()
        window = timedelta(minutes=config.dedup_window_minutes)

        result = await session.execute(
            select(AlertDedupGroup).where(AlertDedupGroup.fingerprint == ctx.alert.fingerprint)
        )
        group = result.scalar_one_or_none()

        if group is None:
            group = AlertDedupGroup(
                fingerprint=ctx.alert.fingerprint,
                first_seen_at=now,
                last_seen_at=now,
                occurrence_count=1,
                window_start=now,
                window_end=now + window,
            )
            session.add(group)
            await session.flush()
            ctx.dedup_group_id = group.id
            ctx.is_representative = True
            return ctx

        if group.window_end >= now and group.representative_alert_id is not None:
            group.occurrence_count += 1
            group.last_seen_at = now
            ctx.dedup_hit = True
            ctx.dedup_group_id = group.id
            ctx.is_representative = False
            ctx.short_circuit = True
            ctx.route_decision = RouteDecision.ARCHIVE_DEDUP
            ctx.route_reason = {
                "summary": "Duplicate alert within dedup window",
                "fingerprint": ctx.alert.fingerprint,
                "occurrence_count": group.occurrence_count,
            }
            return ctx

        if group.window_end < now:
            group.window_start = now
            group.window_end = now + window
            group.first_seen_at = now
            group.last_seen_at = now
            group.occurrence_count = 1
            group.representative_alert_id = None

        ctx.dedup_group_id = group.id
        ctx.is_representative = True
        group.last_seen_at = now
        return ctx
