"""Skill framework base types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import InvestigationContext


class SkillResult(BaseModel):
    success: bool
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
    evidence_ref: str = ""
    cache_key: str | None = None
    error: str | None = None


class Skill(ABC):
    name: ClassVar[str]
    description: ClassVar[str]

    @classmethod
    @abstractmethod
    def parameters_schema(cls) -> dict[str, Any]:
        """OpenAI-compatible JSON Schema for function parameters."""

    @abstractmethod
    async def execute(
        self,
        params: dict[str, Any],
        ctx: InvestigationContext,
        session: AsyncSession,
    ) -> SkillResult:
        """Execute skill and return structured result."""

    @classmethod
    def tool_definition(cls) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": cls.name,
                "description": cls.description,
                "parameters": cls.parameters_schema(),
            },
        }
