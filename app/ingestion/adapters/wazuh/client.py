"""Wazuh Indexer HTTP client with search_after pagination."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.core.datetime_utils import as_naive_utc, utc_now
from app.ingestion.schemas.cursor import CursorState, PullResult, PullStats
from app.ingestion.schemas.wazuh_config import WazuhIndexerConfig

logger = logging.getLogger(__name__)


class IndexerProbeResult:
    """Read-only connectivity and window stats for diagnostics."""

    __slots__ = (
        "connected",
        "http_status",
        "error",
        "latest_timestamp",
        "total_alerts",
        "window_start",
        "window_match_count",
    )

    def __init__(
        self,
        *,
        connected: bool,
        http_status: int | None = None,
        error: str | None = None,
        latest_timestamp: datetime | None = None,
        total_alerts: int | None = None,
        window_start: datetime | None = None,
        window_match_count: int | None = None,
    ) -> None:
        self.connected = connected
        self.http_status = http_status
        self.error = error
        self.latest_timestamp = latest_timestamp
        self.total_alerts = total_alerts
        self.window_start = window_start
        self.window_match_count = window_match_count


class WazuhIndexerClient:
    """OpenSearch-compatible client for wazuh-alerts-* indices."""

    def __init__(self, config: WazuhIndexerConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> WazuhIndexerClient:
        username, password = self.config.resolve_credentials()
        verify: bool | str = self.config.ca_cert_path or self.config.verify_tls
        self._client = httpx.AsyncClient(
            base_url=self.config.indexer_url,
            auth=(username, password),
            verify=verify,
            timeout=self.config.request_timeout_seconds,
            headers={"Content-Type": "application/json"},
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search_alerts(
        self,
        cursor: CursorState,
        *,
        batch_size: int,
    ) -> PullResult:
        if self._client is None:
            raise RuntimeError("Client not initialized; use async with")

        body = self._build_query(cursor, batch_size)
        url = f"/{self.config.index_pattern}/_search"

        response = await self._request_with_retry("POST", url, json=body)
        data = response.json()
        hits = data.get("hits", {}).get("hits", [])

        items = [self._normalize_hit(hit) for hit in hits]
        stats = PullStats(fetched=len(items))
        next_cursor = cursor.model_copy(deep=True)

        if items:
            last_hit = hits[-1]
            last_source = last_hit.get("_source", {})
            last_ts = self._parse_timestamp(last_source)
            next_cursor.last_occurred_at = last_ts
            next_cursor.last_sort_values = last_hit.get("sort")

        next_cursor.last_successful_run_at = utc_now()
        has_more = len(items) >= batch_size

        return PullResult(
            items=items,
            next_cursor=next_cursor,
            has_more=has_more,
            stats=stats,
        )

    async def probe(self, cursor: CursorState) -> IndexerProbeResult:
        """Check Indexer connectivity and how many alerts match the incremental window."""
        if self._client is None:
            raise RuntimeError("Client not initialized; use async with")

        window_start = self._window_start(cursor)
        try:
            latest_response = await self._request_with_retry(
                "POST",
                f"/{self.config.index_pattern}/_search",
                json={
                    "size": 1,
                    "sort": [{"timestamp": {"order": "desc", "unmapped_type": "date"}}],
                    "query": {"match_all": {}},
                },
            )
            latest_data = latest_response.json()
            latest_hits = latest_data.get("hits", {}).get("hits", [])
            latest_ts: datetime | None = None
            if latest_hits:
                latest_ts = self._parse_timestamp(latest_hits[0].get("_source", {}))

            total_raw = latest_data.get("hits", {}).get("total")
            total_alerts: int | None = None
            if isinstance(total_raw, dict):
                total_alerts = int(total_raw.get("value", 0))
            elif isinstance(total_raw, int):
                total_alerts = total_raw

            window_response = await self._request_with_retry(
                "POST",
                f"/{self.config.index_pattern}/_search",
                json={
                    "size": 0,
                    "track_total_hits": True,
                    "query": {
                        "range": {
                            "timestamp": {
                                "gte": window_start.isoformat().replace("+00:00", "Z"),
                            },
                        },
                    },
                },
            )
            window_data = window_response.json()
            window_total_raw = window_data.get("hits", {}).get("total")
            window_count: int | None = None
            if isinstance(window_total_raw, dict):
                window_count = int(window_total_raw.get("value", 0))
            elif isinstance(window_total_raw, int):
                window_count = window_total_raw

            return IndexerProbeResult(
                connected=True,
                http_status=latest_response.status_code,
                latest_timestamp=latest_ts,
                total_alerts=total_alerts,
                window_start=window_start,
                window_match_count=window_count,
            )
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in {401, 403}:
                detail = "认证失败，请检查 WAZUH_INDEXER_USER / WAZUH_INDEXER_PASSWORD"
            else:
                detail = f"Indexer 返回 HTTP {status}"
            return IndexerProbeResult(
                connected=False,
                http_status=status,
                error=detail,
                window_start=window_start,
            )
        except httpx.HTTPError as exc:
            return IndexerProbeResult(
                connected=False,
                error=f"无法连接 Indexer：{exc}",
                window_start=window_start,
            )

    def _window_start(self, cursor: CursorState) -> datetime:
        if cursor.last_occurred_at is None:
            return utc_now() - timedelta(hours=self.config.initial_lookback_hours)
        return as_naive_utc(cursor.last_occurred_at)

    def _build_query(self, cursor: CursorState, batch_size: int) -> dict[str, Any]:
        start = self._window_start(cursor)

        body: dict[str, Any] = {
            "size": batch_size,
            "sort": [
                {"timestamp": {"order": "asc", "unmapped_type": "date"}},
                {"_id": {"order": "asc"}},
            ],
            "query": {
                "range": {
                    "timestamp": {
                        "gte": start.isoformat().replace("+00:00", "Z"),
                    },
                },
            },
        }

        if cursor.last_sort_values:
            body["search_after"] = cursor.last_sort_values

        return body

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any],
        max_retries: int = 3,
    ) -> httpx.Response:
        assert self._client is not None
        delay = 1.0
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                response = await self._client.request(method, url, json=json)
                if response.status_code in {401, 403}:
                    response.raise_for_status()
                if response.status_code >= 500:
                    response.raise_for_status()
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {401, 403}:
                    raise
                last_error = exc
            except httpx.HTTPError as exc:
                last_error = exc

            if attempt < max_retries - 1:
                logger.warning(
                    "Wazuh Indexer request failed (attempt %s/%s): %s",
                    attempt + 1,
                    max_retries,
                    last_error,
                )
                await asyncio.sleep(delay)
                delay *= 2

        assert last_error is not None
        raise last_error

    @staticmethod
    def _normalize_hit(hit: dict[str, Any]) -> dict[str, Any]:
        source = dict(hit.get("_source") or {})
        source["_id"] = hit.get("_id")
        source["_index"] = hit.get("_index")
        if "sort" in hit:
            source["_sort"] = hit["sort"]
        return source

    @staticmethod
    def _parse_timestamp(source: dict[str, Any]) -> datetime:
        raw = source.get("timestamp") or source.get("@timestamp")
        if not raw:
            return utc_now()
        if isinstance(raw, datetime):
            return as_naive_utc(raw)
        text = str(raw).replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return utc_now()
        return as_naive_utc(parsed)
