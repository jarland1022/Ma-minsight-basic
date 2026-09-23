"""Skill registry for Agent tool calling."""

from __future__ import annotations

from typing import Type

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import InvestigationContext
from app.skills.base import Skill, SkillResult
from app.skills.submit_conclusion import SUBMIT_CONCLUSION_NAME, submit_conclusion_tool_definition


class SkillRegistry:
    _skills: dict[str, Skill] = {}

    @classmethod
    def register(cls, skill_cls: Type[Skill]) -> None:
        cls._skills[skill_cls.name] = skill_cls()

    @classmethod
    def tool_definitions(cls, *, include_submit: bool = True) -> list[dict]:
        tools = [skill.tool_definition() for skill in cls._skills.values()]
        if include_submit:
            tools.append(submit_conclusion_tool_definition())
        return tools

    @classmethod
    async def execute(
        cls,
        name: str,
        params: dict,
        ctx: InvestigationContext,
        session: AsyncSession,
    ) -> SkillResult:
        if name == SUBMIT_CONCLUSION_NAME:
            raise ValueError("submit_conclusion must be handled by AgentLoop")
        skill = cls._skills.get(name)
        if skill is None:
            return SkillResult(success=False, summary=f"Unknown skill: {name}", error="unknown_skill")
        return await skill.execute(params, ctx, session)

    @classmethod
    def get(cls, name: str) -> Skill | None:
        return cls._skills.get(name)
