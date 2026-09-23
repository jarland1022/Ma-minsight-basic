"""Human review API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

import app.human_review.adapters.bootstrap  # noqa: F401
from app.api.deps import require_auth, require_pro_license
from app.db.session import get_async_session
from app.human_review.adapters.registry import ImAdapterRegistry
from app.human_review.adapters.wecom.adapter import WeComAdapter
from app.human_review.service import HumanReviewService

router = APIRouter(
    prefix="/api/v1/human-review",
    tags=["human-review"],
    dependencies=[Depends(require_pro_license)],
)


class HumanReviewRunResponse(BaseModel):
    dispatched: int
    expired: int
    cancelled_obsolete: int = 0
    skipped_lock: bool
    skipped_disabled: bool
    errors: list[str]


class SubmitResponseRequest(BaseModel):
    raw_content: str = Field(min_length=1)
    external_msg_id: str | None = None
    responder: str | None = None
    request_id: UUID | None = None


class SubmitResponseResult(BaseModel):
    request_id: str | None
    event_id: str | None
    reinvestigation_triggered: bool
    error: str | None = None


@router.post("/run", response_model=HumanReviewRunResponse, dependencies=[Depends(require_auth)])
async def run_human_review(
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_async_session),
) -> HumanReviewRunResponse:
    service = HumanReviewService(session)
    result = await service.run(limit=limit, use_lock=True)
    return HumanReviewRunResponse(
        dispatched=result.dispatched,
        expired=result.expired,
        cancelled_obsolete=result.cancelled_obsolete,
        skipped_lock=result.skipped_lock,
        skipped_disabled=result.skipped_disabled,
        errors=result.errors,
    )


@router.get("/stats", dependencies=[Depends(require_auth)])
async def human_review_stats(session: AsyncSession = Depends(get_async_session)) -> dict:
    service = HumanReviewService(session)
    return await service.stats()


@router.get("/requests/{request_id}", dependencies=[Depends(require_auth)])
async def get_human_review_request(
    request_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    service = HumanReviewService(session)
    payload = await service.get_request_detail(request_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return payload


@router.post("/requests/{request_id}/cancel", dependencies=[Depends(require_auth)])
async def cancel_human_review_request(
    request_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    service = HumanReviewService(session)
    ok = await service.cancel_request(request_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found or not cancellable")
    return {"cancelled": True}


@router.post("/responses", response_model=SubmitResponseResult, dependencies=[Depends(require_auth)])
async def submit_human_review_response(
    body: SubmitResponseRequest,
    session: AsyncSession = Depends(get_async_session),
) -> SubmitResponseResult:
    service = HumanReviewService(session)
    result = await service.handle_reply(
        raw_content=body.raw_content,
        external_msg_id=body.external_msg_id,
        responder=body.responder,
        request_id=body.request_id,
    )
    return SubmitResponseResult(
        request_id=str(result.request_id) if result.request_id else None,
        event_id=str(result.event_id) if result.event_id else None,
        reinvestigation_triggered=result.reinvestigation_triggered,
        error=result.error,
    )


@router.get("/webhooks/wecom")
async def wecom_webhook_verify(
    msg_signature: str = Query(alias="msg_signature"),
    timestamp: str = Query(),
    nonce: str = Query(),
    echostr: str = Query(),
) -> str:
    adapter = WeComAdapter()
    if not adapter.verify_callback(
        msg_signature=msg_signature,
        timestamp=timestamp,
        nonce=nonce,
        echo_str=echostr,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")
    return echostr


@router.post("/webhooks/wecom")
async def wecom_webhook_inbound(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        raw = await request.body()
        body = {"Content": raw.decode("utf-8", errors="replace")}

    adapter = ImAdapterRegistry.create("wecom")
    inbound = await adapter.parse_callback_body(body)
    if inbound is None:
        return {"status": "ignored"}

    service = HumanReviewService(session)
    result = await service.handle_reply(
        raw_content=inbound.raw_content,
        external_msg_id=inbound.external_msg_id,
        responder=inbound.responder,
    )
    if result.error and result.request_id is None:
        return {"status": "error", "detail": result.error}
    return {
        "status": "ok",
        "request_id": str(result.request_id) if result.request_id else None,
        "reinvestigation_triggered": result.reinvestigation_triggered,
    }
