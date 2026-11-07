"""Prompt assembly tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.agent.context import AlertBrief, EventBrief, InvestigationContext, SopBrief
from app.agent.prompts import build_system_prompt, build_user_prompt


def _ctx(*, simulation_enabled: bool) -> InvestigationContext:
    return InvestigationContext(
        investigation_id=uuid.uuid4(),
        event=EventBrief(
            id=uuid.uuid4(),
            title="brute force",
            primary_category="brute_force",
            queue_priority=1,
            risk_score=80,
            alert_count=1,
            first_alert_at=datetime.now(UTC),
            last_alert_at=datetime.now(UTC),
        ),
        alerts=[
            AlertBrief(
                id=uuid.uuid4(),
                occurred_at=datetime.now(UTC),
                rule_name="SSH brute force",
                severity=10,
                src_ip="1.2.3.4",
            )
        ],
        sop=SopBrief(
            id=uuid.uuid4(),
            name="Brute Force SOP",
            guidance_text="Investigate SSH brute force.",
            recommended_skills=[
                "query_entity_graph",
                "query_asset",
                "simulate_disposition",
            ],
        ),
        disposition_simulation_enabled=simulation_enabled,
    )


def test_prompt_includes_simulation_guidance_when_enabled() -> None:
    prompt = build_system_prompt(_ctx(simulation_enabled=True))
    assert "simulate_disposition" in prompt
    assert "处置推演" in prompt
    assert "高影响" in prompt


def test_prompt_omits_simulation_guidance_when_disabled() -> None:
    prompt = build_system_prompt(_ctx(simulation_enabled=False))
    assert "处置推演（高影响动作前置）" not in prompt


def test_prompt_omits_hypothesis_when_disabled() -> None:
    ctx = _ctx(simulation_enabled=False)
    ctx.hypothesis_template_enabled = False
    prompt = build_system_prompt(ctx)
    assert "假设模板" not in prompt


def test_user_prompt_reminds_simulation_when_enabled() -> None:
    prompt = build_user_prompt(_ctx(simulation_enabled=True))
    assert "simulate_disposition" in prompt
