"""Formal whitelist rule matcher — only path allowed to auto-archive."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now

from app.db.enums import RouteDecision, WhitelistRuleStatus
from app.models.triage import WhitelistRule
from app.triage.config import TriageConfig
from app.triage.handlers.base import TriageHandler
from app.triage.matchers.pattern import match_pattern
from app.triage.schemas.context import TriageContext


class WhitelistHandler(TriageHandler):
    name = "whitelist"

    async def handle(
        self,
        ctx: TriageContext,
        session: AsyncSession,
        config: TriageConfig,
    ) -> TriageContext:
        if ctx.short_circuit:
            ctx.skipped_steps.append(self.name)
            return ctx

        now = utc_now()
        result = await session.execute(
            select(WhitelistRule).where(WhitelistRule.status == WhitelistRuleStatus.ACTIVE)
        )
        rules = result.scalars().all()

        for rule in rules:
            if rule.effective_from > now or rule.effective_until < now:
                continue
            if match_pattern(ctx.alert, rule.match_pattern):
                ctx.whitelist_rule_id = rule.id
                ctx.whitelist_matched = True
                ctx.short_circuit = True
                ctx.route_decision = RouteDecision.ARCHIVE_WHITELIST
                ctx.route_reason = {
                    "summary": f"Matched active whitelist rule: {rule.name}",
                    "whitelist_rule_id": str(rule.id),
                }
                return ctx

        return ctx
