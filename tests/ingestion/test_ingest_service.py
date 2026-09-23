"""Tests for IngestService orchestration (mocked DB)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.enums import AlertStatus
from app.ingestion.schemas.cursor import CursorState, PullResult, PullStats
from app.ingestion.schemas.normalized_alert import NormalizedAlert
from app.ingestion.services.ingest_service import IngestService
from app.models.ingestion import DataSource


def _make_source() -> DataSource:
    source = DataSource(
        id=uuid.uuid4(),
        name="mock_wazuh",
        adapter_type="mock_wazuh",
        config={"fixture_names": ["auth_failed.json"]},
        cursor_state={},
        is_active=True,
    )
    source.updated_at = datetime.now(UTC)
    return source


@pytest.mark.asyncio
async def test_run_for_source_persists_and_updates_cursor() -> None:
    session = AsyncMock()
    source = _make_source()

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = source
    session.execute = AsyncMock(return_value=scalar_result)

    insert_result = MagicMock()
    insert_result.fetchall.return_value = [(uuid.uuid4(),)]
    session.execute = AsyncMock(side_effect=[scalar_result, insert_result])
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()

    service = IngestService(session)

    with patch("app.ingestion.services.ingest_service.ingest_lock") as lock_ctx:
        lock_ctx.return_value.__aenter__ = AsyncMock(return_value=True)
        lock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await service.run_for_source(source.id, max_batches=1)

    assert result.skipped_lock is False
    assert result.total_inserted == 1
    assert source.cursor_state.get("total_ingested") == 1
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_run_for_source_skips_when_lock_busy() -> None:
    session = AsyncMock()
    source = _make_source()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = source
    session.execute = AsyncMock(return_value=scalar_result)

    service = IngestService(session)

    with patch("app.ingestion.services.ingest_service.ingest_lock") as lock_ctx:
        lock_ctx.return_value.__aenter__ = AsyncMock(return_value=False)
        lock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await service.run_for_source(source.id)

    assert result.skipped_lock is True
    assert result.batches == []
