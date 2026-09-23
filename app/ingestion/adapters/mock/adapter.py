"""Mock Wazuh adapter for tests and demos without a live Indexer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar
from uuid import UUID

from app.ingestion.adapters.base import AlertSourceAdapter
from app.ingestion.adapters.registry import AdapterRegistry
from app.ingestion.adapters.wazuh.mapper import extract_source_alert_id, map_wazuh_alert
from app.ingestion.schemas.cursor import CursorState, PullResult, PullStats
from app.ingestion.schemas.normalized_alert import NormalizedAlert

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "wazuh"


class MockWazuhAdapter(AlertSourceAdapter):
    adapter_type: ClassVar[str] = "mock_wazuh"

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self.fixtures_dir = fixtures_dir or FIXTURES_DIR
        self._offset = 0

    async def validate_config(self, config: dict) -> None:
        fixture_names = config.get("fixture_names")
        if fixture_names is not None and not isinstance(fixture_names, list):
            raise ValueError("fixture_names must be a list of JSON filenames")

    async def pull(
        self,
        config: dict,
        cursor: CursorState,
        *,
        batch_size: int = 500,
    ) -> PullResult:
        items = self._load_fixtures(config)
        start = self._offset
        end = min(start + batch_size, len(items))
        batch = items[start:end]
        self._offset = end

        next_cursor = cursor.model_copy(deep=True)
        if batch:
            from app.ingestion.adapters.wazuh.mapper import parse_occurred_at

            next_cursor.last_occurred_at = parse_occurred_at(batch[-1])
            next_cursor.last_sort_values = [
                batch[-1].get("timestamp"),
                batch[-1].get("_id"),
            ]

        from app.core.datetime_utils import utc_now

        next_cursor.last_successful_run_at = utc_now()
        has_more = end < len(items)

        return PullResult(
            items=batch,
            next_cursor=next_cursor,
            has_more=has_more,
            stats=PullStats(fetched=len(batch)),
        )

    def map_to_normalized(
        self,
        raw: dict,
        *,
        data_source_id: UUID,
        data_source_name: str,
    ) -> NormalizedAlert:
        return map_wazuh_alert(
            raw,
            data_source_id=data_source_id,
            data_source_name=data_source_name,
        )

    def extract_source_alert_id(self, raw: dict) -> str:
        return extract_source_alert_id(raw)

    def _load_fixtures(self, config: dict) -> list[dict]:
        names = config.get("fixture_names")
        if not names:
            names = sorted(p.name for p in self.fixtures_dir.glob("*.json"))
        items: list[dict] = []
        for name in names:
            path = self.fixtures_dir / name
            with path.open(encoding="utf-8") as handle:
                doc = json.load(handle)
            doc.setdefault("_id", path.stem)
            items.append(doc)
        return items


AdapterRegistry.register(MockWazuhAdapter.adapter_type, MockWazuhAdapter)
