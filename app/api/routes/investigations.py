"""Investigation API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.orchestrator import InvestigationOrchestrator
from app.api.deps import require_auth, require_pro_license
from app.db.session import get_async_session

router = APIRouter(
    prefix="/api/v1/investigations",
    tags=["investigations"],
    dependencies=[Depends(require_pro_license)],
)


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
    conclusion: dict | None
    tool_calls: list[dict]
    message_count: int


@router.post("/run", response_model=InvestigationRunResponse, dependencies=[Depends(require_auth)])
async def run_investigations(
    limit: int = Query(default=5, ge=1, le=50),
    session: AsyncSession = Depends(get_async_session),
) -> InvestigationRunResponse:
    orchestrator = InvestigationOrchestrator(session)
    result = await orchestrator.run(limit=limit, use_lock=True)
    return InvestigationRunResponse(
        processed=result.processed,
        skipped_lock=result.skipped_lock,
        skipped_budget=result.skipped_budget,
        errors=result.errors,
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
