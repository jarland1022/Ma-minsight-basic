"""Dashboard API."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_auth
from app.console.queries import dashboard_summary
from app.console.rule_noise import list_noisy_rules
from app.db.session import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary", dependencies=[Depends(require_auth)])
async def get_dashboard_summary(session: AsyncSession = Depends(get_async_session)) -> dict:
    try:
        return await dashboard_summary(session)
    except DBAPIError as exc:
        await session.rollback()
        logger.exception("Dashboard summary database error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Dashboard database error — run `docker compose exec app alembic upgrade head`. "
                f"Cause: {exc.orig}"
            ),
        ) from exc
    except SQLAlchemyError as exc:
        await session.rollback()
        logger.exception("Dashboard summary query error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dashboard query error: {exc}",
        ) from exc


@router.get("/noisy-rules", dependencies=[Depends(require_auth)])
async def get_noisy_rules(
    days: int = Query(default=30, ge=1, le=180),
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    try:
        return await list_noisy_rules(session, days=days, limit=limit)
    except DBAPIError as exc:
        await session.rollback()
        logger.exception("Noisy rules database error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Noisy rules query failed: {exc.orig}",
        ) from exc
    except SQLAlchemyError as exc:
        await session.rollback()
        logger.exception("Noisy rules query error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Noisy rules query error: {exc}",
        ) from exc
