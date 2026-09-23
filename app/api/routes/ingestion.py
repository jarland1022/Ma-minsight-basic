"""Ingestion API routes (minimal set)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_auth
from app.core.config import settings
from app.db.session import get_async_session
from app.ingestion.services.ingest_service import IngestService
from app.models.ingestion import DataSource

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])


class DataSourceSummary(BaseModel):
    id: str
    name: str
    adapter_type: str
    is_active: bool


class PullResponse(BaseModel):
    data_source_id: str
    inserted: int
    duplicates: int
    map_errors: int
    batches: int
    skipped_lock: bool


class DataSourceStatus(BaseModel):
    id: str
    name: str
    adapter_type: str
    is_active: bool
    cursor_state: dict
    last_successful_run_at: str | None = None
    total_ingested: int = 0
    updated_at: str | None = None


@router.get("/sources", response_model=list[DataSourceSummary], dependencies=[Depends(require_auth)])
async def list_sources(session: AsyncSession = Depends(get_async_session)) -> list[DataSourceSummary]:
    result = await session.execute(select(DataSource).order_by(DataSource.name))
    sources = result.scalars().all()
    return [
        DataSourceSummary(
            id=str(source.id),
            name=source.name,
            adapter_type=source.adapter_type,
            is_active=source.is_active,
        )
        for source in sources
    ]


@router.post(
    "/sources/{source_id}/pull",
    response_model=PullResponse,
    dependencies=[Depends(require_auth)],
)
async def manual_pull(
    source_id: UUID,
    max_batches: int = Query(default=10, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
) -> PullResponse:
    service = IngestService(session)
    try:
        run_result = await service.run_for_source(
            source_id,
            max_batches=max_batches or settings.ingestion_max_batches_per_run,
            use_lock=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return PullResponse(
        data_source_id=str(run_result.data_source_id),
        inserted=run_result.total_inserted,
        duplicates=run_result.total_duplicates,
        map_errors=sum(b.map_errors for b in run_result.batches),
        batches=len(run_result.batches),
        skipped_lock=run_result.skipped_lock,
    )


@router.get(
    "/sources/{source_id}/status",
    response_model=DataSourceStatus,
    dependencies=[Depends(require_auth)],
)
async def source_status(
    source_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> DataSourceStatus:
    service = IngestService(session)
    status_payload = await service.get_source_status(source_id)
    if status_payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DataSource not found")
    return DataSourceStatus(**status_payload)
