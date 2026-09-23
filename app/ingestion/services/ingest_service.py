"""Ingestion orchestration: pull → map → persist → cursor update."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import as_naive_utc, utc_now
from app.db.enums import ActorType, AlertStatus
from app.geoip.enrich import enrich_src_geo
import app.ingestion.adapters.bootstrap  # noqa: F401 — register adapters
from app.ingestion.adapters.registry import AdapterRegistry
from app.ingestion.lock import ingest_lock
from app.ingestion.schemas.cursor import CursorState
from app.models.ingestion import Alert, DataSource
from app.models.system import AuditLog

logger = logging.getLogger(__name__)


@dataclass
class IngestBatchResult:
    inserted: int = 0
    duplicates: int = 0
    map_errors: int = 0
    fetched: int = 0
    has_more: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class IngestRunResult:
    data_source_id: UUID
    batches: list[IngestBatchResult] = field(default_factory=list)
    skipped_lock: bool = False
    skipped_inactive: bool = False
    skipped_no_adapter: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def total_inserted(self) -> int:
        return sum(batch.inserted for batch in self.batches)

    @property
    def total_duplicates(self) -> int:
        return sum(batch.duplicates for batch in self.batches)


class IngestService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run_for_source(
        self,
        data_source_id: UUID,
        *,
        max_batches: int = 10,
        use_lock: bool = True,
    ) -> IngestRunResult:
        result = IngestRunResult(data_source_id=data_source_id)
        source = await self._get_source(data_source_id)
        if source is None:
            raise ValueError(f"DataSource not found: {data_source_id}")
        if not source.is_active:
            result.skipped_inactive = True
            return result

        async def _execute() -> IngestRunResult:
            adapter = AdapterRegistry.create(source.adapter_type)
            await adapter.validate_config(source.config)
            cursor = CursorState.model_validate(source.cursor_state or {})

            for _ in range(max_batches):
                batch_result = await self._run_batch(source, adapter, cursor)
                result.batches.append(batch_result)
                cursor = CursorState.model_validate(source.cursor_state or {})
                if not batch_result.has_more:
                    break
            return result

        if use_lock:
            async with ingest_lock(str(data_source_id)) as acquired:
                if not acquired:
                    result.skipped_lock = True
                    return result
                return await _execute()
        return await _execute()

    async def run_all_active(self, *, max_batches: int = 10) -> list[IngestRunResult]:
        result = await self.session.execute(
            select(DataSource).where(DataSource.is_active.is_(True))
        )
        sources = result.scalars().all()
        outcomes: list[IngestRunResult] = []
        registered = set(AdapterRegistry.registered_types())
        for source in sources:
            if source.adapter_type not in registered:
                logger.warning(
                    "Skipping data source %s: unknown adapter_type %r (registered: %s)",
                    source.name,
                    source.adapter_type,
                    ", ".join(sorted(registered)),
                )
                skipped = IngestRunResult(data_source_id=source.id)
                skipped.skipped_no_adapter = True
                outcomes.append(skipped)
                continue
            try:
                outcomes.append(
                    await self.run_for_source(source.id, max_batches=max_batches, use_lock=True)
                )
            except Exception as exc:
                logger.exception("Ingestion failed for source=%s", source.name)
                failed = IngestRunResult(data_source_id=source.id)
                failed.errors.append(f"{source.name}: {exc}")
                outcomes.append(failed)
        return outcomes

    async def get_source_status(self, data_source_id: UUID) -> dict[str, Any] | None:
        source = await self._get_source(data_source_id)
        if source is None:
            return None
        cursor = source.cursor_state or {}
        return {
            "id": str(source.id),
            "name": source.name,
            "adapter_type": source.adapter_type,
            "is_active": source.is_active,
            "cursor_state": cursor,
            "last_successful_run_at": cursor.get("last_successful_run_at"),
            "total_ingested": cursor.get("total_ingested", 0),
            "updated_at": source.updated_at.isoformat() if source.updated_at else None,
        }

    async def _run_batch(
        self,
        source: DataSource,
        adapter: Any,
        cursor: CursorState,
    ) -> IngestBatchResult:
        batch_result = IngestBatchResult()
        pull = await adapter.pull(source.config, cursor)
        batch_result.fetched = pull.stats.fetched
        batch_result.has_more = pull.has_more

        rows: list[dict[str, Any]] = []
        now = utc_now()

        for raw in pull.items:
            try:
                normalized = adapter.map_to_normalized(
                    raw,
                    data_source_id=source.id,
                    data_source_name=source.name,
                )
            except Exception as exc:
                batch_result.map_errors += 1
                batch_result.errors.append(str(exc))
                logger.exception("Failed to map alert for source=%s", source.name)
                continue

            enrich_src_geo(normalized)

            rows.append(
                {
                    "data_source_id": source.id,
                    "source_alert_id": normalized.source_alert_id,
                    "fingerprint": normalized.fingerprint,
                    "rule_id": normalized.rule_id,
                    "rule_name": normalized.rule_name,
                    "severity": normalized.severity,
                    "severity_raw": normalized.severity_raw,
                    "occurred_at": as_naive_utc(normalized.occurred_at),
                    "ingested_at": now,
                    "src_ip": normalized.src_ip,
                    "dst_ip": normalized.dst_ip,
                    "src_port": normalized.src_port,
                    "dst_port": normalized.dst_port,
                    "user_name": normalized.user_name,
                    "host_name": normalized.host_name,
                    "process_name": normalized.process_name,
                    "process_cmdline": normalized.process_cmdline,
                    "file_hash": normalized.file_hash,
                    "alert_category": normalized.alert_category,
                    "normalized_fields": normalized.normalized_fields,
                    "raw_data": normalized.raw_data,
                    "status": AlertStatus.NEW,
                }
            )

        inserted = 0
        if rows:
            stmt = (
                insert(Alert)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["data_source_id", "source_alert_id"])
                .returning(Alert.id)
            )
            insert_result = await self.session.execute(stmt)
            inserted = len(insert_result.fetchall())
            batch_result.inserted = inserted
            batch_result.duplicates = len(rows) - inserted

        next_cursor = pull.next_cursor
        next_cursor.total_ingested = cursor.total_ingested + inserted
        source.cursor_state = next_cursor.model_dump(mode="json")
        await self.session.flush()

        self.session.add(
            AuditLog(
                actor_type=ActorType.SYSTEM,
                action="ingestion.batch_completed",
                resource_type="data_source",
                resource_id=str(source.id),
                detail={
                    "inserted": batch_result.inserted,
                    "duplicates": batch_result.duplicates,
                    "map_errors": batch_result.map_errors,
                    "fetched": batch_result.fetched,
                    "has_more": batch_result.has_more,
                },
            )
        )
        await self.session.commit()
        await self.session.refresh(source)
        return batch_result

    async def _get_source(self, data_source_id: UUID) -> DataSource | None:
        result = await self.session.execute(
            select(DataSource).where(DataSource.id == data_source_id)
        )
        return result.scalar_one_or_none()
