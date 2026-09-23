"""Console events API."""

from __future__ import annotations

from typing import Literal

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_auth
from app.console.queries import get_alert_console_detail, get_event_console_detail, list_events
from app.db.enums import EventStatus
from app.db.session import get_async_session

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("", dependencies=[Depends(require_auth)])
async def list_events_api(
    status: EventStatus | None = None,
    category: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: Literal[
        "concluded_at",
        "investigation_finished_at",
        "human_review_sent_at",
        "risk_score",
        "queue_priority",
        "last_alert_at",
    ] | None = None,
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    return await list_events(
        session,
        status=status,
        category=category,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{event_id}", dependencies=[Depends(require_auth)])
async def get_event_detail_api(
    event_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    payload = await get_event_console_detail(session, event_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return payload
