"""Approve/reject disposition simulations — audit only."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import DispositionSimulationApprovalStatus
from app.models.defense_assets import DispositionSimulation


class DispositionSimulationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def approve(
        self,
        simulation_id: UUID,
        *,
        approved_by_id: UUID | None = None,
    ) -> DispositionSimulation | None:
        record = await self.session.get(DispositionSimulation, simulation_id)
        if record is None or record.approval_status != DispositionSimulationApprovalStatus.DRAFT:
            return None
        record.approval_status = DispositionSimulationApprovalStatus.APPROVED
        record.approved_by_id = approved_by_id
        return record

    async def reject(self, simulation_id: UUID) -> bool:
        record = await self.session.get(DispositionSimulation, simulation_id)
        if record is None or record.approval_status != DispositionSimulationApprovalStatus.DRAFT:
            return False
        record.approval_status = DispositionSimulationApprovalStatus.REJECTED
        return True
