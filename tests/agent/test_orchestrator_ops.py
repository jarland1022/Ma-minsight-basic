"""Orchestrator ops failure finalization and auto-pick blocking (T-PICK / T-FAIL)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.agent.failure import blocks_auto_pick
from app.agent.loop import AgentLoopResult
from app.agent.orchestrator import InvestigationOrchestrator
from app.db.enums import EventStatus, InvestigationFailureClass, InvestigationStatus


@pytest.mark.asyncio
async def test_finalize_ops_failure_sets_pending_review_no_conclusion() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    orch = InvestigationOrchestrator(session, agent=MagicMock())

    event = SimpleNamespace(id=uuid4(), status=EventStatus.INVESTIGATING)
    investigation = SimpleNamespace(
        id=uuid4(),
        status=InvestigationStatus.RUNNING,
        finished_at=None,
        error_message=None,
        failure_class=None,
        error_code=None,
        failure_detail=None,
        conclusion=None,
    )
    loop_result = AgentLoopResult(
        investigation_status=InvestigationStatus.FAILED,
        conclusion=None,
        failure_class=InvestigationFailureClass.LLM_SERVICE.value,
        error_code="llm_not_configured",
        error_message="LLM error: DEEPSEEK_API_KEY is not configured",
        is_ops_failure=True,
    )

    import app.agent.orchestrator as orch_mod

    orig = orch_mod.cancel_sent_reviews_for_ops_investigation
    orch_mod.cancel_sent_reviews_for_ops_investigation = AsyncMock(return_value=0)
    try:
        await orch._finalize_ops_failure(event, investigation, loop_result)
    finally:
        orch_mod.cancel_sent_reviews_for_ops_investigation = orig

    assert investigation.status == InvestigationStatus.FAILED
    assert investigation.failure_class == InvestigationFailureClass.LLM_SERVICE.value
    assert investigation.error_code == "llm_not_configured"
    assert event.status == EventStatus.PENDING_REVIEW
    assert blocks_auto_pick(
        status=investigation.status,
        failure_class=investigation.failure_class,
    )


def test_pick_blocks_when_latest_ops_failed() -> None:
    assert blocks_auto_pick(
        status=InvestigationStatus.FAILED,
        failure_class=InvestigationFailureClass.REQUIRED_SKILL.value,
    )
