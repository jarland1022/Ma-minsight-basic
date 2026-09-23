"""Triage API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_auth
from app.db.session import get_async_session
from app.triage.services.triage_service import TriageService

router = APIRouter(prefix="/api/v1/triage", tags=["triage"])


class TriageRunResponse(BaseModel):
    processed: int
    skipped_lock: bool
    errors: list[str]


class TriageStatsResponse(BaseModel):
    route_counts: dict[str, int]


class AlertTriageDetail(BaseModel):
    alert_id: str
    status: str
    fingerprint: str
    triage: dict | None


@router.post("/run", response_model=TriageRunResponse, dependencies=[Depends(require_auth)])
async def run_triage(
    limit: int = Query(default=500, ge=1, le=2000),
    session: AsyncSession = Depends(get_async_session),
) -> TriageRunResponse:
    service = TriageService(session)
    result = await service.run(limit=limit, use_lock=True)
    return TriageRunResponse(
        processed=result.processed,
        skipped_lock=result.skipped_lock,
        errors=result.errors,
    )


@router.get("/stats", response_model=TriageStatsResponse, dependencies=[Depends(require_auth)])
async def triage_stats(session: AsyncSession = Depends(get_async_session)) -> TriageStatsResponse:
    service = TriageService(session)
    return TriageStatsResponse(route_counts=await service.get_stats())


@router.get(
    "/alerts/{alert_id}",
    response_model=AlertTriageDetail,
    dependencies=[Depends(require_auth)],
)
async def alert_triage_detail(
    alert_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> AlertTriageDetail:
    service = TriageService(session)
    payload = await service.get_alert_triage(alert_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return AlertTriageDetail(**payload)
