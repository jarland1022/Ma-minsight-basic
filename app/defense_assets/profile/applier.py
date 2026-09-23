"""Apply approved profile update suggestions to entity memories."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import EntityMemoryType, ProfileUpdateStatus
from app.models.defense_assets import ProfileUpdateSuggestion
from app.models.entity import EntityProfileMemory


class ProfileUpdateApplier:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def apply(self, suggestion_id: UUID) -> EntityProfileMemory | None:
        suggestion = await self.session.get(ProfileUpdateSuggestion, suggestion_id)
        if suggestion is None or suggestion.status != ProfileUpdateStatus.PENDING:
            return None

        changes = suggestion.suggested_changes or {}
        memory_type_raw = changes.get("memory_type", "past_verdict")
        try:
            memory_type = EntityMemoryType(str(memory_type_raw))
        except ValueError:
            memory_type = EntityMemoryType.PAST_VERDICT

        content = changes.get("content")
        if not content:
            return None

        from datetime import UTC, datetime

        memory = EntityProfileMemory(
            entity_profile_id=suggestion.entity_profile_id,
            memory_type=memory_type,
            content=str(content),
            confidence=float(changes.get("confidence", 0.8)),
            source_investigation_id=suggestion.investigation_id,
        )
        self.session.add(memory)
        suggestion.status = ProfileUpdateStatus.APPLIED
        suggestion.applied_at = datetime.now(UTC)
        return memory

    async def reject(self, suggestion_id: UUID) -> bool:
        suggestion = await self.session.get(ProfileUpdateSuggestion, suggestion_id)
        if suggestion is None or suggestion.status != ProfileUpdateStatus.PENDING:
            return False
        suggestion.status = ProfileUpdateStatus.REJECTED
        return True
