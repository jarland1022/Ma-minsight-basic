"""Triage pipeline orchestration."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.triage.config import TriageConfig
from app.triage.handlers.dedup import DedupHandler
from app.triage.handlers.llm_assist import LlmAssistHandler
from app.triage.handlers.persist import PersistHandler
from app.triage.handlers.profile_hint import ProfileHintHandler
from app.triage.handlers.router import RouteHandler
from app.triage.handlers.rule_score import RuleScoreHandler
from app.triage.handlers.whitelist import WhitelistHandler
from app.triage.schemas.context import TriageContext


class TriagePipeline:
    def __init__(self, rng=None) -> None:
        self.handlers = [
            DedupHandler(),
            WhitelistHandler(),
            ProfileHintHandler(),
            RuleScoreHandler(),
            LlmAssistHandler(),
            RouteHandler(rng=rng),
            PersistHandler(),
        ]

    async def run(
        self,
        ctx: TriageContext,
        session: AsyncSession,
        config: TriageConfig,
    ) -> TriageContext:
        for handler in self.handlers:
            ctx = await handler.handle(ctx, session, config)
        return ctx
