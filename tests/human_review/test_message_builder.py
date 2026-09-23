"""Message builder tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.db.enums import InvestigationVerdict, RiskLevel
from app.human_review.message_builder import build_review_message, request_short_code
from app.models.investigation import Event, InvestigationConclusion


def test_build_review_message_contains_evt_tag() -> None:
    request_id = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    event = Event(
        id=uuid.uuid4(),
        event_key="k1",
        title="Brute force",
        primary_category="brute_force",
        risk_score=85.0,
        aggregate_host_name="web-01",
        aggregate_user_name="admin",
    )
    conclusion = InvestigationConclusion(
        investigation_id=uuid.uuid4(),
        verdict=InvestigationVerdict.INSUFFICIENT_INFORMATION,
        confidence=0.4,
        risk_level=RiskLevel.MEDIUM,
        reasoning="Cannot confirm without operator input.",
        human_query="请确认该账号是否在出差？",
        missing_info=["travel status"],
    )
    payload = build_review_message(
        request_id=request_id,
        event=event,
        conclusion=conclusion,
        to_user="@all",
    )
    assert f"#EVT-{request_short_code(request_id)}" in payload.markdown
    assert "出差" in payload.markdown
