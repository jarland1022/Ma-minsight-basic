"""Health-check probe data source — inject-only, no scheduled pull."""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from app.core.datetime_utils import utc_now
from app.ingestion.adapters.base import AlertSourceAdapter
from app.ingestion.adapters.registry import AdapterRegistry
from app.ingestion.schemas.cursor import CursorState, PullResult, PullStats
from app.ingestion.schemas.normalized_alert import NormalizedAlert


class HealthProbeAdapter(AlertSourceAdapter):
    """Alerts for this source are injected by ProbeInjectService, not pulled."""

    adapter_type: ClassVar[str] = "health_probe"

    async def validate_config(self, config: dict) -> None:
        return

    async def pull(
        self,
        config: dict,
        cursor: CursorState,
        *,
        batch_size: int = 500,
    ) -> PullResult:
        next_cursor = cursor.model_copy(deep=True)
        next_cursor.last_successful_run_at = utc_now()
        return PullResult(
            items=[],
            next_cursor=next_cursor,
            has_more=False,
            stats=PullStats(fetched=0),
        )

    def map_to_normalized(
        self,
        raw: dict,
        *,
        data_source_id: UUID,
        data_source_name: str,
    ) -> NormalizedAlert:
        raise NotImplementedError("health_probe alerts are injected via ProbeInjectService")

    def extract_source_alert_id(self, raw: dict) -> str:
        return str(raw.get("_id") or raw.get("id") or "health_probe")


AdapterRegistry.register(HealthProbeAdapter.adapter_type, HealthProbeAdapter)
