"""Alert detail API (linked from events)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_auth
from app.console.queries import get_alert_console_detail
from app.db.session import get_async_session

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("/{alert_id}", dependencies=[Depends(require_auth)])
async def get_alert_detail(
    alert_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    payload = await get_alert_console_detail(session, alert_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return payload
