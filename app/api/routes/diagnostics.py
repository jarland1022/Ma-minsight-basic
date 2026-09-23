"""Operational diagnostics for ingestion and related pipelines."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_auth
from app.db.session import get_async_session
from app.services.ingestion_diagnostics import (
    DataSourceDiagnostics,
    IngestionDiagnosticsReport,
    IngestionDiagnosticsService,
)

router = APIRouter(prefix="/api/v1/diagnostics", tags=["diagnostics"])


class ExtendLookbackRequest(BaseModel):
    lookback_hours: int = Field(default=168, ge=1, le=168)
    reset_cursor: bool = True


@router.get(
    "/ingestion",
    response_model=IngestionDiagnosticsReport,
    dependencies=[Depends(require_auth)],
)
async def ingestion_diagnostics(
    session: AsyncSession = Depends(get_async_session),
) -> IngestionDiagnosticsReport:
    return await IngestionDiagnosticsService(session).run()


@router.post(
    "/ingestion/sources/{source_id}/extend-lookback",
    response_model=DataSourceDiagnostics,
    dependencies=[Depends(require_admin)],
)
async def extend_ingestion_lookback(
    source_id: UUID,
    body: ExtendLookbackRequest,
    session: AsyncSession = Depends(get_async_session),
) -> DataSourceDiagnostics:
    try:
        return await IngestionDiagnosticsService(session).extend_lookback(
            source_id,
            lookback_hours=body.lookback_hours,
            reset_cursor=body.reset_cursor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
