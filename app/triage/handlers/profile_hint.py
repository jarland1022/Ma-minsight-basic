"""Profile hint scorer — reference only, MUST NOT archive."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now

from app.db.enums import EntityType
from app.models.entity import EntityProfile, EntityProfileMemory, OnDutyKnowledge
from app.triage.config import TriageConfig
from app.triage.handlers.base import TriageHandler
from app.triage.schemas.context import TriageContext


class ProfileHintHandler(TriageHandler):
    name = "profile_hint"

    async def handle(
        self,
        ctx: TriageContext,
        session: AsyncSession,
        config: TriageConfig,
    ) -> TriageContext:
        if ctx.short_circuit:
            ctx.skipped_steps.append(self.name)
            return ctx

        score = 0.0
        details: list[str] = []
        now = utc_now()

        entity_keys: list[tuple[EntityType, str | None]] = [
            (EntityType.IP, ctx.alert.src_ip),
            (EntityType.HOST, ctx.alert.host_name),
            (EntityType.USER, ctx.alert.user_name),
        ]

        for entity_type, entity_key in entity_keys:
            if not entity_key:
                continue
            profile = await self._load_profile(session, entity_type, entity_key)
            if profile is None:
                continue

            if profile.is_known_scanner:
                score += 8
                details.append(f"{entity_type.value}:{entity_key} is_known_scanner")
            if profile.is_jump_host:
                score += 5
                details.append(f"{entity_type.value}:{entity_key} is_jump_host")
            if profile.is_decommissioned:
                score += 10
                details.append(f"{entity_type.value}:{entity_key} is_decommissioned")

            memories = await session.execute(
                select(EntityProfileMemory).where(
                    EntityProfileMemory.entity_profile_id == profile.id,
                )
            )
            for memory in memories.scalars():
                if memory.valid_until and memory.valid_until < now:
                    continue
                bonus = min(5.0, memory.confidence * 5.0)
                if bonus > 0:
                    score += bonus
                    details.append(f"memory:{memory.memory_type.value} confidence={memory.confidence}")

        knowledge_rows = await session.execute(
            select(OnDutyKnowledge).where(OnDutyKnowledge.is_active.is_(True))
        )
        for item in knowledge_rows.scalars():
            if item.effective_from > now:
                continue
            if item.effective_until and item.effective_until < now:
                continue
            if self._knowledge_matches(ctx, item.scope):
                score += 5
                details.append(f"on_duty_knowledge:{item.title}")
                break

        ctx.profile_hint_score = min(config.profile_hint_cap, score)
        ctx.profile_hint_details = details
        return ctx

    async def _load_profile(
        self,
        session: AsyncSession,
        entity_type: EntityType,
        entity_key: str,
    ) -> EntityProfile | None:
        result = await session.execute(
            select(EntityProfile).where(
                EntityProfile.entity_type == entity_type,
                EntityProfile.entity_key == entity_key,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _knowledge_matches(ctx: TriageContext, scope: dict) -> bool:
        if not scope:
            return False
        for field, expected in scope.items():
            actual = getattr(ctx.alert, field, None) or ctx.alert.normalized_fields.get(field)
            if actual is None:
                return False
            if isinstance(expected, list):
                if str(actual) not in {str(v) for v in expected}:
                    return False
            elif str(actual) != str(expected):
                return False
        return True
