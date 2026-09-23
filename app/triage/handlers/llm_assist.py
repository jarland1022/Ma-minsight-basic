"""Optional LLM assist scoring for triage (default off)."""

from __future__ import annotations

import hashlib
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import RouteDecision
from app.llm.client import LLMClient
from app.triage.config import TriageConfig
from app.triage.handlers.base import TriageHandler
from app.triage.schemas.context import TriageContext

logger = logging.getLogger(__name__)


def predict_route_decision(score: float, config: TriageConfig) -> RouteDecision:
    """Predict routing before LLM assist adjusts the effective score."""
    if score >= config.deep_review_threshold:
        return RouteDecision.QUEUE_DEEP_REVIEW
    if config.uncertain_band_low <= score < config.uncertain_band_high:
        return RouteDecision.QUEUE_UNCERTAIN
    if score < config.low_risk_threshold:
        return RouteDecision.ARCHIVE_LOW_RISK
    return RouteDecision.QUEUE_UNCERTAIN


class LlmAssistHandler(TriageHandler):
    name = "llm_assist"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    async def handle(
        self,
        ctx: TriageContext,
        session: AsyncSession,
        config: TriageConfig,
    ) -> TriageContext:
        if ctx.short_circuit:
            ctx.skipped_steps.append(self.name)
            return ctx

        if not config.llm_assist_enabled:
            ctx.skipped_steps.append(self.name)
            return ctx

        predicted_route = predict_route_decision(ctx.effective_score, config)
        allowed_routes = {r.lower() for r in config.llm_assist_route_filter}
        if allowed_routes and predicted_route.value not in allowed_routes:
            ctx.skipped_steps.append("llm_assist_route_filtered")
            return ctx

        if config.llm_assist_calls_this_run >= config.llm_assist_max_per_run:
            ctx.skipped_steps.append("llm_assist_max_per_run")
            return ctx

        cache_key = self._cache_key(ctx)
        ctx.llm_cache_key = cache_key

        cached = await self.llm_client.get_cached_score(cache_key)
        if cached is not None:
            ctx.llm_assist_score = cached
        else:
            try:
                ctx.llm_assist_score = await self._score_alert(ctx)
                config.llm_assist_calls_this_run += 1
                await self.llm_client.set_cached_score(cache_key, ctx.llm_assist_score)
            except Exception:
                logger.exception("LLM assist scoring failed for alert=%s", ctx.alert.id)
                ctx.skipped_steps.append("llm_assist_error")

        if ctx.llm_assist_score is not None:
            ctx.effective_score = round(
                ctx.rule_score * (1 - config.llm_weight) + ctx.llm_assist_score * config.llm_weight,
                2,
            )
        return ctx

    async def _score_alert(self, ctx: TriageContext) -> float:
        summary = {
            "rule_id": ctx.alert.rule_id,
            "rule_name": ctx.alert.rule_name,
            "severity": ctx.alert.severity,
            "category": ctx.alert.alert_category,
            "src_ip": ctx.alert.src_ip,
            "host_name": ctx.alert.host_name,
            "user_name": ctx.alert.user_name,
        }
        prompt = (
            "Rate this security alert risk from 0 to 100 (integer). "
            "Reply JSON only: {\"score\": number}\n"
            f"Alert: {json.dumps(summary, ensure_ascii=False)}"
        )
        response = await self.llm_client.complete(prompt)
        return self.llm_client.parse_score(response)

    @staticmethod
    def _cache_key(ctx: TriageContext) -> str:
        payload = f"{ctx.alert.id}|{ctx.alert.rule_id}|{ctx.alert.fingerprint}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"llm_triage:v1:{digest}"
