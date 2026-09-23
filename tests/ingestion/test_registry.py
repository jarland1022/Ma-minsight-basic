"""Tests for mock Wazuh adapter and registry."""

from __future__ import annotations

import uuid

import pytest

import app.ingestion.adapters.bootstrap  # noqa: F401
from app.ingestion.adapters.mock.adapter import MockWazuhAdapter
from app.ingestion.adapters.registry import AdapterRegistry
from app.ingestion.schemas.cursor import CursorState


def test_registry_contains_wazuh_and_mock() -> None:
    types = AdapterRegistry.registered_types()
    assert "wazuh" in types
    assert "mock_wazuh" in types
    assert "health_probe" in types


@pytest.mark.asyncio
async def test_health_probe_adapter_returns_empty_pull() -> None:
    adapter = AdapterRegistry.create("health_probe")
    result = await adapter.pull({}, CursorState(), batch_size=10)
    assert result.items == []
    assert result.has_more is False


@pytest.mark.asyncio
async def test_mock_adapter_pulls_fixtures() -> None:
    adapter = MockWazuhAdapter()
    cursor = CursorState()
    result = await adapter.pull({"fixture_names": ["auth_failed.json"]}, cursor, batch_size=10)

    assert len(result.items) == 1
    assert result.items[0]["_id"] == "wazuh-alert-auth-failed-001"


@pytest.mark.asyncio
async def test_mock_adapter_maps_fixture() -> None:
    adapter = MockWazuhAdapter()
    pull = await adapter.pull({}, CursorState(), batch_size=10)
    normalized = adapter.map_to_normalized(
        pull.items[0],
        data_source_id=uuid.uuid4(),
        data_source_name="mock_wazuh",
    )
    assert normalized.alert_category == "brute_force"
    assert normalized.fingerprint
