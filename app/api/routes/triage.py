"""Triage API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_pipeline_permission, require_auth, require_write
from app.db.session import get_async_session
from app.services.auth import AuthContext
from app.services.pipeline_audit import begin_pipeline_audit, finalize_pipeline_audit
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


@router.post("/run", response_model=TriageRunResponse)
async def run_triage(
    request: Request,
    limit: int = Query(default=500, ge=1, le=2000),
    auth: AuthContext = Depends(require_write),
    session: AsyncSession = Depends(get_async_session),
) -> TriageRunResponse:
    assert_pipeline_permission(auth, "triage")
    started = await begin_pipeline_audit(
        session, request, auth, pipeline="triage", detail={"limit": limit, "source": "triage/run"}
    )
    try:
        result = await TriageService(session).run(limit=limit, use_lock=True)
    except Exception as exc:
        await finalize_pipeline_audit(started.id, success=False, error=str(exc))
        raise
    await finalize_pipeline_audit(
        started.id,
        success=True,
        result_detail={
            "processed": result.processed,
            "skipped_lock": result.skipped_lock,
            "errors": result.errors[:20],
        },
    )
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
