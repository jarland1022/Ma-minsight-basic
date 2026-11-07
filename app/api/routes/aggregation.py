"""Event aggregation API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.aggregation.services.aggregation_service import AggregationService
from app.api.deps import assert_pipeline_permission, require_auth, require_write
from app.db.session import get_async_session
from app.services.auth import AuthContext
from app.services.pipeline_audit import begin_pipeline_audit, finalize_pipeline_audit

router = APIRouter(prefix="/api/v1/aggregation", tags=["aggregation"])


class AggregationRunResponse(BaseModel):
    processed: int
    events_created: int
    events_merged: int
    skipped_lock: bool
    errors: list[str]


class AggregationStatsResponse(BaseModel):
    pending_alerts: int
    events_created_today: int
    avg_alerts_per_event: float


class EventDetailResponse(BaseModel):
    id: str
    event_key: str
    title: str | None
    status: str
    queue_priority: int
    risk_score: float
    alert_count: int
    first_alert_at: str | None
    last_alert_at: str | None
    aggregate_host_name: str | None
    aggregate_user_name: str | None
    aggregate_category: str | None
    aggregate_window_start: str | None
    alerts: list[dict]


@router.post("/run", response_model=AggregationRunResponse)
async def run_aggregation(
    request: Request,
    limit: int = Query(default=500, ge=1, le=2000),
    auth: AuthContext = Depends(require_write),
    session: AsyncSession = Depends(get_async_session),
) -> AggregationRunResponse:
    assert_pipeline_permission(auth, "aggregation")
    started = await begin_pipeline_audit(
        session,
        request,
        auth,
        pipeline="aggregation",
        detail={"limit": limit, "source": "aggregation/run"},
    )
    try:
        result = await AggregationService(session).run(limit=limit, use_lock=True)
    except Exception as exc:
        await finalize_pipeline_audit(started.id, success=False, error=str(exc))
        raise
    await finalize_pipeline_audit(
        started.id,
        success=True,
        result_detail={
            "processed": result.processed,
            "events_created": result.events_created,
            "events_merged": result.events_merged,
            "skipped_lock": result.skipped_lock,
            "errors": result.errors[:20],
        },
    )
    return AggregationRunResponse(
        processed=result.processed,
        events_created=result.events_created,
        events_merged=result.events_merged,
        skipped_lock=result.skipped_lock,
        errors=result.errors,
    )


@router.get("/stats", response_model=AggregationStatsResponse, dependencies=[Depends(require_auth)])
async def aggregation_stats(
    session: AsyncSession = Depends(get_async_session),
) -> AggregationStatsResponse:
    service = AggregationService(session)
    stats = await service.get_stats()
    return AggregationStatsResponse(**stats)


@router.get(
    "/events/{event_id}",
    response_model=EventDetailResponse,
    dependencies=[Depends(require_auth)],
)
async def event_detail(
    event_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> EventDetailResponse:
    service = AggregationService(session)
    payload = await service.get_event_detail(event_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return EventDetailResponse(**payload)
