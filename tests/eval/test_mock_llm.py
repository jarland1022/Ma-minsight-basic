"""Mock regression LLM tests."""

import pytest

from app.db.enums import InvestigationVerdict
from app.eval.regression.alert_builder import build_regression_context
from app.eval.regression.mock_llm import MockRegressionLLM


@pytest.mark.asyncio
async def test_mock_regression_llm_replays_fixture() -> None:
    llm = MockRegressionLLM("brute_force_fp")
    resp1 = await llm.chat(messages=[], tools=[], model="mock")
    assert resp1.tool_calls[0].name == "query_asset"
    resp2 = await llm.chat(messages=[], tools=[], model="mock")
    assert resp2.tool_calls[0].name == "query_history_alerts"
    resp3 = await llm.chat(messages=[], tools=[], model="mock")
    assert resp3.tool_calls[0].name == "submit_conclusion"
    assert "query_asset" in llm.skills_called


def test_build_regression_context() -> None:
    inv, ctx = build_regression_context(
        "brute_force_fp",
        {
            "alert_category": "brute_force",
            "host_name": "web-01",
            "occurred_at": "2026-06-23T08:00:00Z",
        },
    )
    assert ctx.event.primary_category == "brute_force"
    assert inv.event_id == ctx.event.id
