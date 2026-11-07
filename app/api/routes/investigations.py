"""Investigation API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.orchestrator import InvestigationOrchestrator
from app.api.deps import assert_pipeline_permission, require_admin, require_auth, require_write
from app.db.session import get_async_session
from app.services.auth import AuthContext
from app.services.pipeline_audit import begin_pipeline_audit, finalize_pipeline_audit

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])


class InvestigationRunResponse(BaseModel):
    processed: int
    skipped_lock: bool
    skipped_budget: bool
    errors: list[str]


class InvestigationDetailResponse(BaseModel):
    id: str
    event_id: str
    status: str
    model_name: str
    token_input: int
    token_output: int
    skill_call_count: int
    current_step: int
    error_message: str | None = None
    failure_class: str | None = None
    error_code: str | None = None
    conclusion: dict | None
    tool_calls: list[dict]
    message_count: int


class ReinvestigateResponse(BaseModel):
    investigation_id: str | None
    skipped_lock: bool
    error: str | None = None


@router.post("/run", response_model=InvestigationRunResponse)
async def run_investigations(
    request: Request,
    limit: int = Query(default=5, ge=1, le=50),
    auth: AuthContext = Depends(require_write),
    session: AsyncSession = Depends(get_async_session),
) -> InvestigationRunResponse:
    assert_pipeline_permission(auth, "investigation")
    started = await begin_pipeline_audit(
        session,
        request,
        auth,
        pipeline="investigation",
        detail={"limit": limit, "source": "investigations/run"},
    )
    try:
        result = await InvestigationOrchestrator(session).run(limit=limit, use_lock=True)
    except Exception as exc:
        await finalize_pipeline_audit(started.id, success=False, error=str(exc))
        raise
    await finalize_pipeline_audit(
        started.id,
        success=True,
        result_detail={
            "processed": result.processed,
            "skipped_lock": result.skipped_lock,
            "skipped_budget": result.skipped_budget,
            "errors": result.errors[:20],
        },
    )
    return InvestigationRunResponse(
        processed=result.processed,
        skipped_lock=result.skipped_lock,
        skipped_budget=result.skipped_budget,
        errors=result.errors,
    )


@router.post(
    "/events/{event_id}/reinvestigate",
    response_model=ReinvestigateResponse,
    dependencies=[Depends(require_admin)],
)
async def reinvestigate_event(
    event_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> ReinvestigateResponse:
    """Explicit admin re-run after ops failure / config fix. Creates a new Investigation."""
    orchestrator = InvestigationOrchestrator(session)
    result = await orchestrator.reinvestigate_event(event_id, use_lock=True)
    if result.error and result.investigation_id is None and not result.skipped_lock:
        code = (
            status.HTTP_404_NOT_FOUND
            if result.error == "Event not found"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=code, detail=result.error)
    return ReinvestigateResponse(
        investigation_id=str(result.investigation_id) if result.investigation_id else None,
        skipped_lock=result.skipped_lock,
        error=result.error,
    )


@router.get("/stats/summary", dependencies=[Depends(require_auth)])
async def investigation_stats(session: AsyncSession = Depends(get_async_session)) -> dict:
    from sqlalchemy import func, select

    from app.models.investigation import Investigation

    count_result = await session.execute(select(func.count()).select_from(Investigation))
    token_result = await session.execute(
        select(func.sum(Investigation.token_input), func.sum(Investigation.token_output))
    )
    tokens = token_result.one()
    return {
        "total_investigations": int(count_result.scalar_one() or 0),
        "total_token_input": int(tokens[0] or 0),
        "total_token_output": int(tokens[1] or 0),
    }


@router.get(
    "/{investigation_id}",
    response_model=InvestigationDetailResponse,
    dependencies=[Depends(require_auth)],
)
async def get_investigation(
    investigation_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> InvestigationDetailResponse:
    orchestrator = InvestigationOrchestrator(session)
    payload = await orchestrator.get_investigation_detail(investigation_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")
    return InvestigationDetailResponse(**payload)


@router.get("/{investigation_id}/trace", dependencies=[Depends(require_auth)])
async def get_investigation_trace(
    investigation_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    orchestrator = InvestigationOrchestrator(session)
    payload = await orchestrator.get_trace(investigation_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")
    return payload
