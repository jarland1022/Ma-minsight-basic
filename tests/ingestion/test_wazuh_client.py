"""Tests for Wazuh Indexer client search_after pagination."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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
async def test_search_alerts_builds_search_after(indexer_config: WazuhIndexerConfig) -> None:
    client = WazuhIndexerClient(indexer_config)
    cursor = CursorState(
        last_occurred_at=datetime(2026, 6, 23, 8, 0, tzinfo=UTC),
        last_sort_values=["2026-06-23T08:00:00.000Z", "abc"],
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "hits": {
            "hits": [
                {
                    "_id": "alert-1",
                    "_source": {"timestamp": "2026-06-23T08:15:30.000Z", "rule": {"id": "1"}},
                    "sort": ["2026-06-23T08:15:30.000Z", "alert-1"],
                }
            ]
        }
    }

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_response)

    with patch.object(WazuhIndexerClient, "__aenter__", return_value=client):
        client._client = mock_http
        result = await client.search_alerts(cursor, batch_size=100)

    assert len(result.items) == 1
    assert result.items[0]["_id"] == "alert-1"
    assert result.next_cursor.last_sort_values == ["2026-06-23T08:15:30.000Z", "alert-1"]
    assert result.has_more is False

    call_kwargs = mock_http.request.call_args.kwargs
    body = call_kwargs["json"]
    assert body["search_after"] == ["2026-06-23T08:00:00.000Z", "abc"]
    assert body["size"] == 100


@pytest.mark.asyncio
async def test_search_alerts_initial_lookback(indexer_config: WazuhIndexerConfig) -> None:
    client = WazuhIndexerClient(indexer_config)
    cursor = CursorState()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"hits": {"hits": []}}

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_response)
    client._client = mock_http

    result = await client.search_alerts(cursor, batch_size=50)

    body = mock_http.request.call_args.kwargs["json"]
    assert "search_after" not in body
    assert result.stats.fetched == 0


@pytest.mark.asyncio
async def test_auth_error_not_retried(indexer_config: WazuhIndexerConfig) -> None:
    client = WazuhIndexerClient(indexer_config)
    cursor = CursorState()

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(
        return_value=mock_response,
    )
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Unauthorized",
        request=MagicMock(),
        response=mock_response,
    )
    client._client = mock_http

    with pytest.raises(httpx.HTTPStatusError):
        await client.search_alerts(cursor, batch_size=10)

    assert mock_http.request.call_count == 1
