"""Persist triage results and update alert status."""

from __future__ import annotations

from datetime import datetime
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now

from app.db.enums import AlertStatus, AuditSampleReason, RouteDecision
from app.models.human_review import AuditSample
from app.models.ingestion import Alert, AlertDedupGroup
from app.models.triage import TriageResult
from app.triage.config import TriageConfig
from app.triage.handlers.base import TriageHandler
from app.triage.schemas.context import TriageContext


ARCHIVE_ROUTES = {
    RouteDecision.ARCHIVE_LOW_RISK,
    RouteDecision.ARCHIVE_WHITELIST,
    RouteDecision.ARCHIVE_DEDUP,
    RouteDecision.SAMPLE_AUDIT,
}

QUEUE_ROUTES = {
    RouteDecision.QUEUE_DEEP_REVIEW,
    RouteDecision.QUEUE_UNCERTAIN,
}


class PersistHandler(TriageHandler):
    name = "persist"

    async def handle(
        self,
        ctx: TriageContext,
        session: AsyncSession,
        config: TriageConfig,
    ) -> TriageContext:
        if ctx.route_decision is None:
            raise ValueError("route_decision must be set before persist")

        now = utc_now()
        route_reason_text = json.dumps(ctx.route_reason, ensure_ascii=False)

        session.add(
            TriageResult(
                alert_id=ctx.alert.id,
                dedup_hit=ctx.dedup_hit,
                profile_hint_score=ctx.profile_hint_score,
                whitelist_rule_id=ctx.whitelist_rule_id,
                rule_score=ctx.rule_score,
                llm_assist_score=ctx.llm_assist_score,
                llm_cache_key=ctx.llm_cache_key,
                route_decision=ctx.route_decision,
                route_reason=route_reason_text,
                triaged_at=now,
            )
        )

        alert = await session.get(Alert, ctx.alert.id)
        if alert is None:
            raise ValueError(f"Alert not found: {ctx.alert.id}")

        if ctx.dedup_group_id:
            alert.dedup_group_id = ctx.dedup_group_id

        if ctx.route_decision in ARCHIVE_ROUTES:
            alert.status = AlertStatus.ARCHIVED
        elif ctx.route_decision in QUEUE_ROUTES:
            alert.status = AlertStatus.TRIAGED
        else:
            alert.status = AlertStatus.TRIAGED

        if ctx.is_representative and ctx.dedup_group_id:
            group = await session.get(AlertDedupGroup, ctx.dedup_group_id)
            if group and group.representative_alert_id is None:
                group.representative_alert_id = ctx.alert.id

        if ctx.route_decision == RouteDecision.SAMPLE_AUDIT:
            session.add(
                AuditSample(
                    alert_id=ctx.alert.id,
                    sample_reason=AuditSampleReason.LOW_RISK_RANDOM,
                    reviewed_at=None,
                )
            )

        return ctx
