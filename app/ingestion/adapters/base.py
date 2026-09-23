"""Alert source adapter abstract base."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar
from uuid import UUID

from app.ingestion.schemas.cursor import CursorState, PullResult
from app.ingestion.schemas.normalized_alert import NormalizedAlert


class AlertSourceAdapter(ABC):
    adapter_type: ClassVar[str]

    @abstractmethod
    async def validate_config(self, config: dict) -> None:
        """Validate adapter-specific config before pull."""

    @abstractmethod
    async def pull(
        self,
        config: dict,
        cursor: CursorState,
        *,
        batch_size: int = 500,
    ) -> PullResult:
        """Fetch a batch of raw alerts from upstream."""

    @abstractmethod
    def map_to_normalized(
        self,
        raw: dict,
        *,
        data_source_id: UUID,
        data_source_name: str,
    ) -> NormalizedAlert:
        """Map raw upstream document to NormalizedAlert (pure, testable)."""

    @abstractmethod
    def extract_source_alert_id(self, raw: dict) -> str:
        """Stable idempotency key component from raw document."""
