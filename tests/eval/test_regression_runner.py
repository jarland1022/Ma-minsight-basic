"""Regression runner mock-session compatibility."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.skills.bootstrap  # noqa: F401
from app.agent.config import InvestigationConfig
from app.agent.loop import AgentLoop
from app.db.enums import InvestigationVerdict
from app.defense_assets.disposition.config import DispositionConfig
from app.eval.evaluators.verdict_skills import evaluate_case
from app.eval.regression.alert_builder import build_regression_context
from app.eval.regression.mock_llm import MockRegressionLLM


@pytest.mark.asyncio
async def test_regression_mock_path_with_disposition_config_patch() -> None:
    """AgentLoop loads disposition config from DB; regression uses AsyncMock session."""
    inv, ctx = build_regression_context(
        "brute_force_fp",
        {
            "rule_id": "5710",
            "rule_name": "sshd authentication failed",
            "severity": 4,
            "src_ip": "203.0.113.50",
            "user_name": "root",
            "host_name": "web-server-01",
            "alert_category": "brute_force",
            "occurred_at": "2026-06-23T08:15:30Z",
        },
    )
    mock_llm = MockRegressionLLM("brute_force_fp")
    skills_called = mock_llm.skills_called
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    import app.agent.loop as loop_module

    async def mock_execute(name, params, ctx, session):
        from app.skills.base import SkillResult

        skills_called.append(name)
        return SkillResult(success=True, summary=f"mock {name}", evidence_ref=f"mock:{name}")

    original = loop_module.SkillRegistry.execute
    loop_module.SkillRegistry.execute = mock_execute
    disp_mock = AsyncMock(return_value=DispositionConfig())
    try:
        with patch("app.agent.loop.load_disposition_config", disp_mock):
            loop_result = await AgentLoop(llm=mock_llm).run(
                mock_session,
                inv,
                ctx,
                InvestigationConfig(max_steps=20, model_name=ctx.model_name),
            )
    finally:
        loop_module.SkillRegistry.execute = original

    result = evaluate_case(
        case_id="1",
        case_name="brute_force_fp",
        expected_verdict=InvestigationVerdict.LIKELY_FALSE_POSITIVE,
        expected_skills=["query_asset", "query_history_alerts"],
        forbidden_skills=[],
        actual_verdict=loop_result.conclusion.verdict,
        actual_skills=list(loop_result.skills_called or skills_called),
        require_closure_pass=True,
        closure_passed=(
            loop_result.closure_result.passed if loop_result.closure_result else None
        ),
    )
    assert result.passed, (
        f"verdict={result.actual_verdict} skills={result.actual_skills} "
        f"closure_ok={result.closure_ok} error={result.error}"
    )
