"""Rule-based triage scoring."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AssetCriticality, EntityType
from app.models.entity import EntityProfile
from app.triage.config import TriageConfig
from app.triage.handlers.base import TriageHandler
from app.triage.schemas.context import TriageContext
from app.triage.scoring.category_risk import category_risk_score
from app.triage.scoring.frequency import frequency_score_from_count, get_frequency_count
from app.triage.scoring.severity import severity_score

CRITICALITY_SCORE = {
    AssetCriticality.CRITICAL: 100.0,
    AssetCriticality.HIGH: 80.0,
    AssetCriticality.MEDIUM: 60.0,
    AssetCriticality.LOW: 40.0,
}


class RuleScoreHandler(TriageHandler):
    name = "rule_score"

    async def handle(
        self,
        ctx: TriageContext,
        session: AsyncSession,
        config: TriageConfig,
    ) -> TriageContext:
        if ctx.short_circuit:
            ctx.skipped_steps.append(self.name)
            return ctx

        sev = severity_score(ctx.alert.severity)
        freq_count = await get_frequency_count(session, ctx.alert)
        freq = frequency_score_from_count(freq_count)
        asset = await self._asset_score(session, ctx)
        category = category_risk_score(ctx.alert.alert_category, config.category_risk)

        rule_score = sev * 0.4 + freq * 0.3 + asset * 0.2 + category * 0.1
        discount = min(
            config.profile_hint_score_discount_cap,
            ctx.profile_hint_score * 0.3,
        )
        rule_score = max(0.0, rule_score - discount)

        ctx.rule_score = round(rule_score, 2)
        ctx.rule_score_breakdown = {
            "severity": round(sev, 2),
            "frequency": round(freq, 2),
            "frequency_count": float(freq_count),
            "asset": round(asset, 2),
            "category": round(category, 2),
            "profile_discount": round(discount, 2),
        }
        ctx.effective_score = ctx.rule_score
        return ctx

    async def _asset_score(self, session: AsyncSession, ctx: TriageContext) -> float:
        if not ctx.alert.host_name:
            return 60.0
        result = await session.execute(
            select(EntityProfile).where(
                EntityProfile.entity_type == EntityType.HOST,
                EntityProfile.entity_key == ctx.alert.host_name,
            )
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            return 60.0
        return CRITICALITY_SCORE.get(profile.asset_criticality, 60.0)
