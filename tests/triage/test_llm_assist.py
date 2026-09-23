"""LLM assist handler tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.triage.config import TriageConfig
from app.triage.handlers.llm_assist import LlmAssistHandler
from app.triage.schemas.context import AlertSnapshot, TriageContext


def _ctx() -> TriageContext:
    return TriageContext(
        alert=AlertSnapshot(
            id=uuid.uuid4(),
            data_source_id=uuid.uuid4(),
            data_source_name="wazuh",
            source_alert_id="1",
            fingerprint="fp",
            severity=3,
            occurred_at=datetime.now(UTC),
        ),
        rule_score=50.0,
        effective_score=50.0,
    )


@pytest.mark.asyncio
async def test_llm_disabled_skips() -> None:
    handler = LlmAssistHandler(llm_client=MagicMock())
    ctx = await handler.handle(_ctx(), AsyncMock(), TriageConfig(llm_assist_enabled=False))
    assert ctx.llm_assist_score is None
    assert "llm_assist" in ctx.skipped_steps


@pytest.mark.asyncio
async def test_llm_enabled_uses_cache() -> None:
    client = MagicMock()
    client.get_cached_score = AsyncMock(return_value=80.0)
    client.set_cached_score = AsyncMock()
    handler = LlmAssistHandler(llm_client=client)
    config = TriageConfig(llm_assist_enabled=True, llm_weight=0.15)
    ctx = await handler.handle(_ctx(), AsyncMock(), config)
    assert ctx.llm_assist_score == 80.0
    assert ctx.effective_score == pytest.approx(50 * 0.85 + 80 * 0.15)
    client.complete.assert_not_called()


@pytest.mark.asyncio
async def test_llm_route_filter_skips_deep_review() -> None:
    handler = LlmAssistHandler(llm_client=MagicMock())
    ctx = _ctx()
    ctx.effective_score = 85.0
    config = TriageConfig(
        llm_assist_enabled=True,
        llm_assist_route_filter=["queue_uncertain"],
        deep_review_threshold=70.0,
    )
    ctx = await handler.handle(ctx, AsyncMock(), config)
    assert ctx.llm_assist_score is None
    assert "llm_assist_route_filtered" in ctx.skipped_steps


@pytest.mark.asyncio
async def test_llm_uncertain_band_runs() -> None:
    client = MagicMock()
    client.get_cached_score = AsyncMock(return_value=55.0)
    client.set_cached_score = AsyncMock()
    handler = LlmAssistHandler(llm_client=client)
    ctx = _ctx()
    ctx.effective_score = 50.0
    config = TriageConfig(
        llm_assist_enabled=True,
        llm_assist_route_filter=["queue_uncertain"],
        uncertain_band_low=30.0,
        uncertain_band_high=70.0,
    )
    ctx = await handler.handle(ctx, AsyncMock(), config)
    assert ctx.llm_assist_score == 55.0


def test_llm_parse_score_json() -> None:
    from app.llm.client import LLMClient

    assert LLMClient.parse_score('{"score": 72}') == 72.0
