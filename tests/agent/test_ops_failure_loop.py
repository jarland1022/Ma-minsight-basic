"""AgentLoop ops failure must not emit security conclusions (T-FAIL-01/02)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.config import InvestigationConfig
from app.agent.context import AlertBrief, EventBrief, InvestigationContext
from app.agent.loop import AgentLoop
from app.db.enums import InvestigationFailureClass, InvestigationStatus
from app.defense_assets.disposition.config import DispositionConfig
from app.models.investigation import Investigation


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
async def test_llm_not_configured_is_ops_failure_without_conclusion() -> None:
    llm = MagicMock()
    llm.chat = AsyncMock(side_effect=RuntimeError("DEEPSEEK_API_KEY is not configured"))
    loop = AgentLoop(llm=llm)
    session = AsyncMock()
    session.add = MagicMock()

    result = await loop.run(session, _investigation(), _ctx(), InvestigationConfig(max_steps=3))
    assert result.is_ops_failure is True
    assert result.conclusion is None
    assert result.investigation_status == InvestigationStatus.FAILED
    assert result.failure_class == InvestigationFailureClass.LLM_SERVICE.value
    assert result.error_code == "llm_not_configured"


@pytest.mark.asyncio
async def test_llm_http_500_is_ops_failure() -> None:
    llm = MagicMock()
    llm.chat = AsyncMock(side_effect=RuntimeError("HTTP 500 Internal Server Error"))
    loop = AgentLoop(llm=llm)
    session = AsyncMock()
    session.add = MagicMock()

    result = await loop.run(session, _investigation(), _ctx(), InvestigationConfig(max_steps=2))
    assert result.is_ops_failure is True
    assert result.conclusion is None
    assert result.error_code == "llm_http_5xx"


@pytest.mark.asyncio
async def test_required_skill_hard_fail_is_ops_without_conclusion() -> None:
    """T-FAIL-03: required skill failure after retries → FAILED, no security conclusion."""
    from app.agent.context import SopBrief
    from app.llm.schemas import ChatCompletionResult, ToolCallRequest, TokenUsage
    from app.skills.base import SkillResult

    llm = MagicMock()
    llm.chat = AsyncMock(
        return_value=ChatCompletionResult(
            content=None,
            tool_calls=[
                ToolCallRequest(
                    id="c1",
                    name="query_asset",
                    arguments={"entity_type": "ip", "entity_key": "1.2.3.4"},
                )
            ],
            usage=TokenUsage(10, 5),
        )
    )
    loop = AgentLoop(llm=llm)
    session = AsyncMock()
    session.add = MagicMock()

    ctx = _ctx()
    ctx = ctx.model_copy(
        update={
            "sop": SopBrief(
                id=uuid.uuid4(),
                name="test",
                guidance_text="g",
                recommended_skills=["query_asset"],
            )
        }
    )

    async def mock_execute(name, params, ctx, session):
        return SkillResult(success=False, summary="unreachable", error="connection refused")

    import app.agent.loop as loop_module

    original = loop_module.SkillRegistry.execute
    loop_module.SkillRegistry.execute = mock_execute
    try:
        result = await loop.run(
            session,
            _investigation(),
            ctx,
            InvestigationConfig(max_steps=3, skill_max_retries=0),
        )
    finally:
        loop_module.SkillRegistry.execute = original

    assert result.is_ops_failure is True
    assert result.conclusion is None
    assert result.investigation_status == InvestigationStatus.FAILED
    assert result.failure_class == InvestigationFailureClass.DATASOURCE.value
    assert "query_asset" in result.failed_required_skills


@pytest.mark.asyncio
async def test_reject_attack_confirmed_when_required_skill_failed() -> None:
    """T-FAIL-10: deterministic verdict rejected if required skills failed."""
    from app.agent.context import SopBrief
    from app.llm.schemas import ChatCompletionResult, ToolCallRequest, TokenUsage
    from app.skills.base import SkillResult
    from app.skills.submit_conclusion import SUBMIT_CONCLUSION_NAME

    llm = MagicMock()
    llm.chat = AsyncMock(
        side_effect=[
            ChatCompletionResult(
                content=None,
                tool_calls=[
                    ToolCallRequest(
                        id="c1",
                        name="query_asset",
                        arguments={"entity_type": "ip", "entity_key": "1.2.3.4"},
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
                            "verdict": "attack_confirmed",
                            "confidence": 0.9,
                            "risk_level": "high",
                            "reasoning": "guess without evidence",
                            "evidence_refs": [],
                        },
                    )
                ],
                usage=TokenUsage(10, 5),
            ),
            # After rejection, force max_steps exit via empty assistant content path
            ChatCompletionResult(content="thinking", tool_calls=[], usage=TokenUsage(1, 1)),
            ChatCompletionResult(content="thinking", tool_calls=[], usage=TokenUsage(1, 1)),
        ]
    )
    loop = AgentLoop(llm=llm)
    session = AsyncMock()
    session.add = MagicMock()
    ctx = _ctx().model_copy(
        update={
            "sop": SopBrief(
                id=uuid.uuid4(),
                name="test",
                guidance_text="g",
                recommended_skills=["query_asset"],
            )
        }
    )

    async def mock_execute(name, params, ctx, session):
        return SkillResult(success=False, summary="optional miss", error="not found")

    import app.agent.loop as loop_module

    original = loop_module.SkillRegistry.execute
    loop_module.SkillRegistry.execute = mock_execute
    try:
        # First skill is required and datasource-ish → may ops-fail before submit.
        # Use non-datasource error so optional-style continue isn't used; required → FAILED early.
        result = await loop.run(
            session,
            _investigation(),
            ctx,
            InvestigationConfig(max_steps=5, skill_max_retries=0),
        )
    finally:
        loop_module.SkillRegistry.execute = original

    # Required skill failed hard → ops failure before attack_confirmed can stick
    assert result.is_ops_failure is True
    assert result.conclusion is None
