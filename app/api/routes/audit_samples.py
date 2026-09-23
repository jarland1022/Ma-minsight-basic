"""Audit sample API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_auth
from app.db.enums import InvestigationVerdict
from app.db.session import get_async_session
from app.human_review.audit_sampler import AuditSampleService

router = APIRouter(prefix="/api/v1/audit-samples", tags=["audit-samples"])


class AuditSampleRunResponse(BaseModel):
    created: int
    skipped_disabled: bool
    errors: list[str]


class AuditReviewRequest(BaseModel):
    review_verdict: InvestigationVerdict
    is_correct: bool | None = None
    feedback: str | None = None


@router.post("/run", response_model=AuditSampleRunResponse, dependencies=[Depends(require_auth)])
async def run_audit_samples(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
) -> AuditSampleRunResponse:
    service = AuditSampleService(session)
    result = await service.run(limit=limit)
    return AuditSampleRunResponse(
        created=result.created,
        skipped_disabled=result.skipped_disabled,
        errors=result.errors,
    )


@router.post("/{sample_id}/review", dependencies=[Depends(require_auth)])
async def submit_audit_review(
    sample_id: UUID,
    body: AuditReviewRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    service = AuditSampleService(session)
    ok = await service.submit_review(
        sample_id,
        review_verdict=body.review_verdict,
        is_correct=body.is_correct,
        feedback=body.feedback,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit sample not found")
    return {"reviewed": True}
