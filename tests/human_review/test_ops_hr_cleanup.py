"""Structured ops HR cancel — must not rely on regex alone (T-HR-CLEAN)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.db.enums import HumanReviewStatus, InvestigationStatus
from app.human_review.stale import (
    cancel_sent_reviews_for_ops_investigation,
    is_system_error_human_query,
    list_ambiguous_system_error_reviews,
)


@pytest.mark.asyncio
async def test_cancel_ops_investigation_sets_reason() -> None:
    session = AsyncMock()
    inv_id = uuid4()
    event_id = uuid4()
    req = SimpleNamespace(
        id=uuid4(),
        investigation_id=inv_id,
        event_id=event_id,
        status=HumanReviewStatus.SENT,
        question="自动调查未完成：LLM error",
        cancel_reason=None,
        cancelled_at=None,
        cancelled_by=None,
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [req]
    session.execute = AsyncMock(return_value=result)

    n = await cancel_sent_reviews_for_ops_investigation(
        session,
        investigation_id=inv_id,
        event_id=event_id,
        reason="ops_failure_reclassification",
        actor="system",
    )
    assert n == 1
    assert req.status == HumanReviewStatus.CANCELLED
    assert req.cancel_reason == "ops_failure_reclassification"
    assert req.cancelled_by == "system"
    assert req.cancelled_at is not None


@pytest.mark.asyncio
async def test_ambiguous_list_excludes_structured_ops() -> None:
    session = AsyncMock()
    inv = SimpleNamespace(
        status=InvestigationStatus.FAILED,
        failure_class="llm_service",
        conclusion=None,
    )
    req_structured = SimpleNamespace(
        question="自动调查未完成：LLM error: x，请协助确认。",
        investigation=inv,
        status=HumanReviewStatus.SENT,
    )
    req_ambiguous = SimpleNamespace(
        question="自动调查未完成：LLM error: y，请协助确认。",
        investigation=SimpleNamespace(
            status=InvestigationStatus.NEEDS_HUMAN,
            failure_class=None,
            conclusion=SimpleNamespace(invalidated_as_ops_failure=False),
        ),
        status=HumanReviewStatus.SENT,
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [req_structured, req_ambiguous]
    session.execute = AsyncMock(return_value=result)

    out = await list_ambiguous_system_error_reviews(session)
    assert req_ambiguous in out
    assert req_structured not in out


def test_regex_helper_still_exists_for_ui_only() -> None:
    assert is_system_error_human_query("自动调查未完成：LLM error: 404 Not Found，请协助确认。")
