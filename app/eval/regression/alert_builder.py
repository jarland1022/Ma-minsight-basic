"""Build in-memory investigation context from regression case payload."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.agent.context import AlertBrief, EventBrief, InvestigationContext
from app.models.investigation import Investigation


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if value is None:
        return datetime.now(UTC)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.now(UTC)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def build_regression_context(
    case_name: str,
    alert_payload: dict[str, Any],
    *,
    model_name: str = "mock-regression",
) -> tuple[Investigation, InvestigationContext]:
    event_id = uuid4()
    investigation_id = uuid4()
    alert_id = uuid4()
    occurred_at = _parse_dt(alert_payload.get("occurred_at"))

    ctx = InvestigationContext(
        investigation_id=investigation_id,
        event=EventBrief(
            id=event_id,
            title=alert_payload.get("title") or f"Regression: {case_name}",
            primary_category=alert_payload.get("alert_category"),
            queue_priority=int(alert_payload.get("queue_priority", 10)),
            risk_score=float(alert_payload.get("risk_score", 70)),
            alert_count=1,
            first_alert_at=occurred_at,
            last_alert_at=occurred_at,
            aggregate_host_name=alert_payload.get("host_name"),
            aggregate_user_name=alert_payload.get("user_name"),
        ),
        alerts=[
            AlertBrief(
                id=alert_id,
                occurred_at=occurred_at,
                rule_id=alert_payload.get("rule_id"),
                rule_name=alert_payload.get("rule_name"),
                severity=int(alert_payload.get("severity", 4)),
                src_ip=alert_payload.get("src_ip"),
                user_name=alert_payload.get("user_name"),
                host_name=alert_payload.get("host_name"),
                alert_category=alert_payload.get("alert_category"),
                triage_rule_score=float(alert_payload.get("triage_rule_score", 75)),
                triage_route=alert_payload.get("triage_route", "queue_deep_review"),
            )
        ],
        model_name=model_name,
    )
    investigation = Investigation(
        id=investigation_id,
        event_id=event_id,
        model_name=model_name,
        max_steps=5,
        current_step=0,
        token_input=0,
        token_output=0,
        skill_call_count=0,
        started_at=datetime.now(UTC),
    )
    return investigation, ctx
