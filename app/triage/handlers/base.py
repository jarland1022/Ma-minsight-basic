"""Triage handler base class."""

from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.triage.config import TriageConfig
from app.triage.schemas.context import TriageContext


class TriageHandler(ABC):
    name: str

    @abstractmethod
    async def handle(
        self,
        ctx: TriageContext,
        session: AsyncSession,
        config: TriageConfig,
    ) -> TriageContext:
        """Mutate and return triage context."""
