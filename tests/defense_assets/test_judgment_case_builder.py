"""Judgment case builder helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.defense_assets.builders.judgment_case import build_entity_tags, build_investigation_trace
from app.models.investigation import Event, InvestigationToolCall


def test_build_entity_tags_from_event() -> None:
    event = Event(
        id=uuid.uuid4(),
        event_key="k",
        primary_category="brute_force",
        aggregate_host_name="web-01",
        aggregate_user_name="admin",
        risk_score=1.0,
    )
    tags = build_entity_tags(event, [])
    assert tags["category"] == "brute_force"
    assert tags["host"] == "web-01"


def test_build_investigation_trace_sorted() -> None:
    inv_id = uuid.uuid4()
    calls = [
        InvestigationToolCall(
            investigation_id=inv_id,
            step_number=2,
            skill_name="query_asset",
            skill_input={},
            skill_output={},
            output_summary="asset ok",
            called_at=datetime.now(UTC),
        ),
        InvestigationToolCall(
            investigation_id=inv_id,
            step_number=1,
            skill_name="query_history_alerts",
            skill_input={},
            skill_output={},
            output_summary="history ok",
            called_at=datetime.now(UTC),
        ),
    ]
    trace = build_investigation_trace(calls)
    assert trace[0]["step"] == 1
    assert trace[1]["step"] == 2
