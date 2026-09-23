"""Wazuh Indexer alert source adapter."""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from app.ingestion.adapters.base import AlertSourceAdapter
from app.ingestion.adapters.registry import AdapterRegistry
from app.ingestion.adapters.wazuh.client import WazuhIndexerClient
from app.ingestion.adapters.wazuh.mapper import extract_source_alert_id, map_wazuh_alert
from app.ingestion.schemas.cursor import CursorState, PullResult
from app.ingestion.schemas.normalized_alert import NormalizedAlert
from app.ingestion.schemas.wazuh_config import WazuhIndexerConfig


class WazuhAdapter(AlertSourceAdapter):
    adapter_type: ClassVar[str] = "wazuh"

    async def validate_config(self, config: dict) -> None:
        parsed = WazuhIndexerConfig.model_validate(config)
        parsed.resolve_credentials()

    async def pull(
        self,
        config: dict,
        cursor: CursorState,
        *,
        batch_size: int = 500,
    ) -> PullResult:
        parsed = WazuhIndexerConfig.model_validate(config)
        effective_batch = min(batch_size, parsed.batch_size)
        async with WazuhIndexerClient(parsed) as client:
            return await client.search_alerts(cursor, batch_size=effective_batch)

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


AdapterRegistry.register(WazuhAdapter.adapter_type, WazuhAdapter)
