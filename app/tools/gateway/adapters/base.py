"""Tool gateway adapter base types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class ToolGatewayAdapter(ABC):
    name: str

    @abstractmethod
    async def invoke(
        self,
        operation: str,
        params: dict[str, Any],
        *,
        session: AsyncSession | None = None,
        timeout_seconds: int = 30,
    ) -> dict[str, Any]:
        """Execute adapter operation and return structured JSON."""
