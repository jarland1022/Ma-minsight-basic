"""Agent loop tests with mocked LLM."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.config import InvestigationConfig
from app.agent.context import AlertBrief, EventBrief, InvestigationContext
from app.agent.loop import AgentLoop
from app.defense_assets.disposition.config import DispositionConfig
from app.db.enums import InvestigationVerdict, RiskLevel
from app.llm.schemas import ChatCompletionResult, ToolCallRequest, TokenUsage
from app.models.investigation import Investigation
from app.skills.submit_conclusion import SUBMIT_CONCLUSION_NAME


@pytest.fixture(autouse=True)
def _mock_disposition_config(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _load(_session: object) -> DispositionConfig:
        return DispositionConfig(simulation_enabled=False)

    monkeypatch.setattr("app.agent.loop.load_disposition_config", _load)


def _investigation() -> Investigation:
    return Investigation(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        model_name="deepseek-chat",
        max_steps=5,
        current_step=0,
        token_input=0,
        token_output=0,
        skill_call_count=0,
        started_at=datetime.now(UTC),
    )


def _ctx() -> InvestigationContext:
    return InvestigationContext(
        investigation_id=uuid.uuid4(),
        event=EventBrief(
            id=uuid.uuid4(),
            title="test event",
            primary_category="brute_force",
            alert_count=1,
        ),
        alerts=[
            AlertBrief(
                id=uuid.uuid4(),
                occurred_at=datetime.now(UTC),
                severity=4,
                src_ip="203.0.113.1",
            )
        ],
    )


@pytest.mark.asyncio
async def test_agent_loop_submits_conclusion() -> None:
    llm = MagicMock()
    llm.chat = AsyncMock(
        return_value=ChatCompletionResult(
            content=None,
            tool_calls=[
                ToolCallRequest(
                    id="call_1",
                    name=SUBMIT_CONCLUSION_NAME,
                    arguments={
                        "verdict": "likely_false_positive",
                        "confidence": 0.8,
                        "risk_level": "medium",
                        "reasoning": "No successful login observed.",
                        "evidence_refs": ["history:ip:203.0.113.1"],
                    },
                )
            ],
            usage=TokenUsage(100, 50),
        )
    )
    session = AsyncMock()
    session.add = MagicMock()
    loop = AgentLoop(llm=llm)
    result = await loop.run(session, _investigation(), _ctx(), InvestigationConfig(max_steps=3))

    assert result.conclusion.verdict == InvestigationVerdict.LIKELY_FALSE_POSITIVE
    assert llm.chat.await_count == 1


@pytest.mark.asyncio
async def test_agent_loop_calls_skill_then_submit() -> None:
    llm = MagicMock()
    llm.chat = AsyncMock(
        side_effect=[
            ChatCompletionResult(
                content=None,
                tool_calls=[
                    ToolCallRequest(
                        id="c1",
                        name="query_asset",
                        arguments={"entity_type": "ip", "entity_key": "203.0.113.1"},
                    )
                ],
                usage=TokenUsage(10, 5),
            ),
            ChatCompletionResult(
                content=None,
                tool_calls=[
                    ToolCallRequest(
                        id="c2",
                        name=SUBMIT_CONCLUSION_NAME,
                        arguments={
                            "verdict": "needs_human_review",
                            "confidence": 0.4,
                            "risk_level": "high",
                            "reasoning": "Need more context",
                            "human_query": "请确认是否允许该IP访问？",
                        },
                    )
                ],
                usage=TokenUsage(10, 5),
            ),
        ]
    )

    session = AsyncMock()
    session.add = MagicMock()

    loop = AgentLoop(llm=llm)

    async def mock_execute(name, params, ctx, session):
        from app.skills.base import SkillResult

        return SkillResult(
            success=True,
            summary="No profile found",
            evidence_ref="asset:ip:203.0.113.1",
        )

    import app.agent.loop as loop_module

    original = loop_module.SkillRegistry.execute
    loop_module.SkillRegistry.execute = mock_execute
    try:
        result = await loop.run(session, _investigation(), _ctx(), InvestigationConfig(max_steps=5))
    finally:
        loop_module.SkillRegistry.execute = original

    assert result.conclusion.verdict == InvestigationVerdict.NEEDS_HUMAN_REVIEW
    assert llm.chat.await_count == 2
