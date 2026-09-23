"""Tests for ingestion diagnostics service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.ingestion.adapters.wazuh.client import IndexerProbeResult
from app.ingestion.schemas.cursor import CursorState
from app.models.ingestion import DataSource
from app.services.ingestion_diagnostics import IngestionDiagnosticsService


def _wazuh_source(**overrides: object) -> DataSource:
    source = DataSource(
        id=uuid4(),
        name="wazuh",
        adapter_type="wazuh",
        is_active=True,
        config={
            "indexer_url": "https://indexer.local:9200",
            "index_pattern": "wazuh-alerts-*",
            "initial_lookback_hours": 24,
            "verify_tls": False,
        },
        cursor_state={"version": 1, "mode": "search_after"},
    )
    for key, value in overrides.items():
        setattr(source, key, value)
    return source


@pytest.mark.asyncio
async def test_diagnose_wazuh_lookback_gap() -> None:
    source = _wazuh_source(cursor_state={"version": 1, "mode": "search_after"})
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    latest = datetime(2026, 6, 26, 14, 50, tzinfo=UTC)
    window_start = now.replace(tzinfo=None) - timedelta(hours=24)

    probe = IndexerProbeResult(
        connected=True,
        http_status=200,
        latest_timestamp=latest.replace(tzinfo=None),
        total_alerts=7297,
        window_start=window_start,
        window_match_count=0,
    )

    session = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 7297
    session.execute = AsyncMock(return_value=count_result)

    service = IngestionDiagnosticsService(session)
    with (
        patch("app.services.ingestion_diagnostics.utc_now", return_value=now.replace(tzinfo=None)),
        patch("app.services.ingestion_diagnostics.WazuhIndexerConfig.resolve_credentials", return_value=("u", "p")),
        patch("app.services.ingestion_diagnostics.WazuhIndexerClient") as client_cls,
    ):
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.probe = AsyncMock(return_value=probe)
        client_cls.return_value = client

        report = await service._diagnose_source(source)

    assert report.overall_status == "warn"
    assert "extend_lookback" in report.actions_available
    gap = next(c for c in report.checks if c.id == "lookback_gap")
    assert gap.status == "warn"
    assert "24" in gap.message


@pytest.mark.asyncio
async def test_diagnose_health_probe_info() -> None:
    source = DataSource(
        id=uuid4(),
        name="health_probe",
        adapter_type="health_probe",
        is_active=True,
        config={},
        cursor_state={},
    )
    session = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    session.execute = AsyncMock(return_value=count_result)

    service = IngestionDiagnosticsService(session)
    report = await service._diagnose_source(source)

    assert report.overall_status == "ok"
    assert any(c.id == "health_probe" for c in report.checks)


@pytest.mark.asyncio
async def test_extend_lookback_updates_config() -> None:
    source = _wazuh_source()
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    service = IngestionDiagnosticsService(session)
    service._get_source = AsyncMock(return_value=source)
    service._diagnose_source = AsyncMock(return_value=MagicMock())

    await service.extend_lookback(source.id, lookback_hours=168, reset_cursor=True)

    assert source.config["initial_lookback_hours"] == 168
    assert source.cursor_state["last_occurred_at"] is None
    session.commit.assert_awaited_once()
