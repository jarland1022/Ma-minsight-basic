"""Route decision engine."""

from __future__ import annotations

import random

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import RouteDecision
from app.triage.config import TriageConfig
from app.triage.handlers.base import TriageHandler
from app.triage.schemas.context import TriageContext


class RouteHandler(TriageHandler):
    name = "router"

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()

    async def handle(
        self,
        ctx: TriageContext,
        session: AsyncSession,
        config: TriageConfig,
    ) -> TriageContext:
        if ctx.route_decision is not None:
            return ctx

        score = ctx.effective_score
        low = config.low_risk_threshold
        deep = config.deep_review_threshold
        band_low = config.uncertain_band_low
        band_high = config.uncertain_band_high

        if score >= deep:
            ctx.route_decision = RouteDecision.QUEUE_DEEP_REVIEW
            ctx.route_reason = {
                "summary": f"effective_score={score} >= deep_review_threshold({deep})",
                "effective_score": score,
                "breakdown": ctx.rule_score_breakdown,
                "profile_hints": ctx.profile_hint_details,
            }
            return ctx

        if band_low <= score < band_high:
            ctx.route_decision = RouteDecision.QUEUE_UNCERTAIN
            ctx.route_reason = {
                "summary": f"effective_score={score} in uncertain band [{band_low}, {band_high})",
                "effective_score": score,
                "breakdown": ctx.rule_score_breakdown,
            }
            return ctx

        if score < low:
            if self.rng.random() < config.sample_audit_rate:
                ctx.route_decision = RouteDecision.SAMPLE_AUDIT
                ctx.route_reason = {
                    "summary": f"effective_score={score} < low_threshold({low}), selected for sample audit",
                    "effective_score": score,
                }
            else:
                ctx.route_decision = RouteDecision.ARCHIVE_LOW_RISK
                ctx.route_reason = {
                    "summary": f"effective_score={score} < low_threshold({low})",
                    "effective_score": score,
                }
            return ctx

        ctx.route_decision = RouteDecision.QUEUE_UNCERTAIN
        ctx.route_reason = {
            "summary": f"effective_score={score} default uncertain queue",
            "effective_score": score,
        }
        return ctx
