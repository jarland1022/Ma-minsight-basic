"""Tests for Wazuh Indexer probe diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ingestion.adapters.wazuh.client import WazuhIndexerClient
from app.ingestion.schemas.cursor import CursorState
from app.ingestion.schemas.wazuh_config import WazuhIndexerConfig


@pytest.fixture
def indexer_config(monkeypatch: pytest.MonkeyPatch) -> WazuhIndexerConfig:
    monkeypatch.setenv("WAZUH_INDEXER_USER", "admin")
    monkeypatch.setenv("WAZUH_INDEXER_PASSWORD", "secret")
    return WazuhIndexerConfig(indexer_url="https://indexer.local:9200")


@pytest.mark.asyncio
async def test_probe_returns_window_stats(indexer_config: WazuhIndexerConfig) -> None:
    client = WazuhIndexerClient(indexer_config)
    cursor = CursorState()

    latest_response = MagicMock()
    latest_response.status_code = 200
    latest_response.json.return_value = {
        "hits": {
            "total": {"value": 100, "relation": "eq"},
            "hits": [
                {
                    "_source": {"timestamp": "2026-06-26T22:50:18.104+0800"},
                }
            ],
        }
    }

    window_response = MagicMock()
    window_response.status_code = 200
    window_response.json.return_value = {
        "hits": {"total": {"value": 0, "relation": "eq"}, "hits": []},
    }

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(side_effect=[latest_response, window_response])
    client._client = mock_http

    result = await client.probe(cursor)

    assert result.connected is True
    assert result.total_alerts == 100
    assert result.window_match_count == 0
    assert result.latest_timestamp is not None
