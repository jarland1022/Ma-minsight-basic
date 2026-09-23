"""Query recent alerts for an entity."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import InvestigationContext
from app.core.datetime_utils import hours_ago
from app.models.ingestion import Alert
from app.models.investigation import Event, EventAlert
from app.models.triage import TriageResult
from app.services.system_config import get_config_bool, get_config_int
from app.skills.base import Skill, SkillResult

FIELD_MAP = {
    "ip": Alert.src_ip,
    "host": Alert.host_name,
    "user": Alert.user_name,
}


class QueryHistoryAlertsSkill(Skill):
    name = "query_history_alerts"
    description = "Query recent alerts for an IP, host, or user within a time window."

    @classmethod
    def parameters_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "entity_type": {"type": "string", "enum": ["ip", "host", "user"]},
                "entity_key": {"type": "string"},
                "window_hours": {"type": "integer", "default": 24},
                "limit": {"type": "integer", "default": 50},
                "mode": {
                    "type": "string",
                    "enum": ["alerts", "correlated_events"],
                    "default": "alerts",
                    "description": "alerts=raw alerts; correlated_events=events sharing entity",
                },
            },
            "required": ["entity_type", "entity_key"],
        }

    async def execute(
        self,
        params: dict[str, Any],
        ctx: InvestigationContext,
        session: AsyncSession,
    ) -> SkillResult:
        entity_type = str(params.get("entity_type", "")).lower()
        entity_key = str(params.get("entity_key", "")).strip()
        window_hours = int(
            params.get("window_hours")
            or await get_config_int(session, "investigation.correlation_window_hours", 72)
        )
        limit = min(int(params.get("limit") or 50), 100)
        mode = str(params.get("mode") or "alerts").lower()

        column = FIELD_MAP.get(entity_type)
        if column is None or not entity_key:
            return SkillResult(success=False, summary="Invalid entity_type or entity_key", error="invalid_params")

        if mode == "correlated_events":
            return await self._correlated_events(
                session, entity_type, entity_key, window_hours, limit, ctx
            )

        since = hours_ago(window_hours)
        if entity_type == "ip":
            filter_clause = column == entity_key
        else:
            filter_clause = column == entity_key

        result = await session.execute(
            select(Alert, TriageResult)
            .outerjoin(TriageResult, TriageResult.alert_id == Alert.id)
            .where(filter_clause, Alert.occurred_at >= since)
            .order_by(Alert.occurred_at.desc())
            .limit(limit)
        )
        rows = result.all()
        alerts = [
            {
                "occurred_at": alert.occurred_at.isoformat(),
                "rule_name": alert.rule_name,
                "severity": alert.severity,
                "alert_category": alert.alert_category,
                "source_alert_id": alert.source_alert_id,
                "triage_score": triage.rule_score if triage else None,
            }
            for alert, triage in rows
        ]
        data = {"total": len(alerts), "window_hours": window_hours, "alerts": alerts}
        summary = (
            f"Found {len(alerts)} alerts for {entity_type}:{entity_key} in last {window_hours}h."
        )[:500]
        return SkillResult(
            success=True,
            summary=summary,
            data=data,
            evidence_ref=f"history:{entity_type}:{entity_key}",
        )

    async def _correlated_events(
        self,
        session: AsyncSession,
        entity_type: str,
        entity_key: str,
        window_hours: int,
        limit: int,
        ctx: InvestigationContext,
    ) -> SkillResult:
        since = hours_ago(window_hours)
        column = FIELD_MAP[entity_type]
        alert_ids_subq = select(Alert.id).where(column == entity_key, Alert.occurred_at >= since)
        result = await session.execute(
            select(Event)
            .join(EventAlert, EventAlert.event_id == Event.id)
            .where(EventAlert.alert_id.in_(alert_ids_subq))
            .order_by(Event.last_alert_at.desc())
            .limit(limit)
        )
        events = result.scalars().all()
        items = [
            {
                "event_id": str(ev.id),
                "title": ev.title,
                "status": ev.status.value,
                "risk_score": ev.risk_score,
                "alert_count": ev.alert_count,
                "host": ev.aggregate_host_name,
                "user": ev.aggregate_user_name,
                "category": ev.primary_category,
            }
            for ev in events
        ]

        auto_raise = await get_config_bool(
            session, "investigation.auto_raise_priority_on_correlation", True
        )
        if auto_raise and len(items) > 1:
            current = await session.get(Event, ctx.event.id)
            if current is not None:
                related_ids = [ev.id for ev in events if ev.id != current.id]
                if related_ids:
                    current.queue_priority = min(current.queue_priority + 1, 100)
                    current.correlation_key = f"{entity_type}:{entity_key}"
                    merged = list(current.related_event_ids or [])
                    for rid in related_ids:
                        if rid not in merged:
                            merged.append(rid)
                    current.related_event_ids = merged[:20]

        summary = (
            f"Found {len(items)} events correlated with {entity_type}:{entity_key} "
            f"in last {window_hours}h."
        )[:500]
        return SkillResult(
            success=True,
            summary=summary,
            data={"total": len(items), "events": items, "mode": "correlated_events"},
            evidence_ref=f"correlated_events:{entity_type}:{entity_key}",
        )
