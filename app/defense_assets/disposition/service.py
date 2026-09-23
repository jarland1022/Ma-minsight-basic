"""Disposition record confirm/reject — audit only, no enforcement."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now
from app.db.enums import DispositionStatus
from app.models.defense_assets import DispositionRecord


class DispositionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def confirm(
        self,
        record_id: UUID,
        *,
        confirmed_action: str | None = None,
        confirmed_by_id: UUID | None = None,
    ) -> DispositionRecord | None:
        record = await self.session.get(DispositionRecord, record_id)
        if record is None or record.status != DispositionStatus.SUGGESTED:
            return None
        record.status = DispositionStatus.CONFIRMED
        record.confirmed_action = confirmed_action or record.suggested_action
        record.confirmed_by_id = confirmed_by_id
        record.confirmed_at = utc_now()
        return record

    async def reject(self, record_id: UUID) -> bool:
        record = await self.session.get(DispositionRecord, record_id)
        if record is None or record.status != DispositionStatus.SUGGESTED:
            return False
        record.status = DispositionStatus.REJECTED
        record.confirmed_at = utc_now()
        return True
