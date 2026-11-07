"""Morning Note digest API."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_auth
from app.db.session import get_async_session
from app.services.auth import AuthContext
from app.services.morning_note import build_morning_note

router = APIRouter(prefix="/api/v1/morning-note", tags=["morning-note"])


@router.get("")
async def get_morning_note(
    hours: float = Query(15.0, ge=1, le=168, description="Lookback window in hours"),
    since: datetime | None = Query(None, description="Window start (UTC, overrides hours)"),
    until: datetime | None = Query(None, description="Window end (UTC, default now)"),
    timezone_label: str = Query("UTC", max_length=64),
    worth_limit: int = Query(5, ge=1, le=20),
    _auth: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    return await build_morning_note(
        session,
        hours=None if since else hours,
        since=since,
        until=until,
        timezone_label=timezone_label,
        worth_limit=worth_limit,
    )
