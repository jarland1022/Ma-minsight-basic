"""Build a chronological behavior timeline around an investigation anchor.

Uses stored alerts only (no invented events). Each row carries a source_ref
so analysts / the agent can spot-check timestamps back to the original alert.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import InvestigationContext
from app.core.datetime_utils import as_naive_utc
from app.models.ingestion import Alert
from app.models.investigation import EventAlert
from app.skills.base import Skill, SkillResult

FIELD_MAP = {
    "ip": Alert.src_ip,
    "host": Alert.host_name,
    "user": Alert.user_name,
}


def _classify(alert: Alert) -> str:
    blob = f"{alert.alert_category or ''} {alert.rule_name or ''}".lower()
    if "dns" in blob:
        return "dns"
    if any(k in blob for k in ("auth", "login", "brute", "ssh", "rdp", "vpn")):
        return "authentication"
    if any(k in blob for k in ("malware", "virus", "c2", "beacon", "ransomware", "trojan")):
        return "malware_c2"
    if any(k in blob for k in ("phish", "bec", "mail", "email")):
        return "email"
    if alert.file_hash or alert.process_name:
        return "endpoint"
    if alert.dst_ip or alert.dst_port:
        return "network"
    return "alert"


def _row_summary(alert: Alert, kind: str) -> str:
    bits: list[str] = []
    if alert.rule_name:
        bits.append(alert.rule_name)
    if alert.src_ip and alert.dst_ip:
        port = f":{alert.dst_port}" if alert.dst_port else ""
        bits.append(f"{alert.src_ip} → {alert.dst_ip}{port}")
    elif alert.dst_ip:
        port = f":{alert.dst_port}" if alert.dst_port else ""
        bits.append(f"dst {alert.dst_ip}{port}")
    elif alert.src_ip:
        bits.append(f"src {alert.src_ip}")
    if alert.user_name:
        bits.append(f"user={alert.user_name}")
    if alert.host_name:
        bits.append(f"host={alert.host_name}")
    if alert.process_name:
        bits.append(f"proc={alert.process_name}")
    if alert.file_hash:
        bits.append(f"hash={alert.file_hash[:16]}…")
    if not bits:
        bits.append(kind)
    return "; ".join(bits)[:240]


class QueryBehaviorTimelineSkill(Skill):
    name = "query_behavior_timeline"
    description = (
        "Build a chronological behavior timeline for a host/IP/user around the event "
        "time window (default: 30 minutes before → 10 minutes after). Returns only "
        "stored alerts with source_ref for back-checking; does not invent activity."
    )

    @classmethod
    def parameters_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["ip", "host", "user"],
                    "description": "Entity to center the timeline on. Defaults from event context.",
                },
                "entity_key": {
                    "type": "string",
                    "description": "Entity value. Defaults to event aggregate host/user or first alert src_ip.",
                },
                "minutes_before": {
                    "type": "integer",
                    "default": 30,
                    "description": "Minutes before anchor time to include",
                },
                "minutes_after": {
                    "type": "integer",
                    "default": 10,
                    "description": "Minutes after anchor time to include",
                },
                "limit": {"type": "integer", "default": 40},
                "include_event_alerts": {
                    "type": "boolean",
                    "default": True,
                    "description": "Always include alerts linked to the current event",
                },
            },
            "required": [],
        }

    async def execute(
        self,
        params: dict[str, Any],
        ctx: InvestigationContext,
        session: AsyncSession,
    ) -> SkillResult:
        entity_type, entity_key = self._resolve_entity(params, ctx)
        minutes_before = max(0, min(int(params.get("minutes_before") or 30), 24 * 60))
        minutes_after = max(0, min(int(params.get("minutes_after") or 10), 24 * 60))
        limit = min(int(params.get("limit") or 40), 100)
        include_event = bool(params.get("include_event_alerts", True))

        anchor = as_naive_utc(ctx.event.last_alert_at or ctx.event.first_alert_at)
        window_start = anchor - timedelta(minutes=minutes_before)
        window_end = anchor + timedelta(minutes=minutes_after)

        alerts_by_id: dict[Any, Alert] = {}

        if include_event:
            event_rows = await session.execute(
                select(Alert)
                .join(EventAlert, EventAlert.alert_id == Alert.id)
                .where(EventAlert.event_id == ctx.event.id)
                .order_by(Alert.occurred_at.asc())
            )
            for alert in event_rows.scalars().all():
                alerts_by_id[alert.id] = alert

        if entity_type and entity_key:
            column = FIELD_MAP[entity_type]
            # Also match dst_ip when entity is IP (outbound destination / C2)
            if entity_type == "ip":
                filter_clause = or_(Alert.src_ip == entity_key, Alert.dst_ip == entity_key)
            else:
                filter_clause = column == entity_key
            entity_rows = await session.execute(
                select(Alert)
                .where(
                    filter_clause,
                    Alert.occurred_at >= window_start,
                    Alert.occurred_at <= window_end,
                )
                .order_by(Alert.occurred_at.asc())
                .limit(limit)
            )
            for alert in entity_rows.scalars().all():
                alerts_by_id[alert.id] = alert

        ordered = sorted(
            alerts_by_id.values(),
            key=lambda a: as_naive_utc(a.occurred_at),
        )[:limit]

        timeline: list[dict[str, Any]] = []
        kind_counts: dict[str, int] = {}
        for idx, alert in enumerate(ordered, start=1):
            kind = _classify(alert)
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
            timeline.append(
                {
                    "seq": idx,
                    "occurred_at": as_naive_utc(alert.occurred_at).isoformat(),
                    "source_ref": f"alert:{alert.source_alert_id}",
                    "alert_id": str(alert.id),
                    "kind": kind,
                    "summary": _row_summary(alert, kind),
                    "rule_name": alert.rule_name,
                    "severity": alert.severity,
                    "alert_category": alert.alert_category,
                    "src_ip": str(alert.src_ip) if alert.src_ip else None,
                    "dst_ip": str(alert.dst_ip) if alert.dst_ip else None,
                    "dst_port": alert.dst_port,
                    "user_name": alert.user_name,
                    "host_name": alert.host_name,
                    "process_name": alert.process_name,
                    "file_hash": alert.file_hash,
                }
            )

        data = {
            "entity_type": entity_type,
            "entity_key": entity_key,
            "anchor_at": anchor.isoformat(),
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "minutes_before": minutes_before,
            "minutes_after": minutes_after,
            "total": len(timeline),
            "kind_counts": kind_counts,
            "timeline": timeline,
            "verification": {
                "rule": "Only stored alerts are listed. Verify timestamps via source_ref / alert_id.",
                "do_not": "Do not invent DNS queries, sessions, or hashes not present in timeline[].",
            },
        }
        if not timeline:
            summary = (
                f"No alerts in timeline for {entity_type or 'event'}:{entity_key or ctx.event.id} "
                f"window {minutes_before}m before → {minutes_after}m after anchor."
            )
        else:
            summary = (
                f"Timeline {len(timeline)} events for {entity_type}:{entity_key} "
                f"({minutes_before}m/-{minutes_after}m); kinds={kind_counts}"
            )
        return SkillResult(
            success=True,
            summary=summary[:500],
            data=data,
            evidence_ref=f"timeline:{entity_type or 'event'}:{entity_key or ctx.event.id}",
        )

    @staticmethod
    def _resolve_entity(
        params: dict[str, Any],
        ctx: InvestigationContext,
    ) -> tuple[str | None, str | None]:
        entity_type = str(params.get("entity_type") or "").lower().strip() or None
        entity_key = str(params.get("entity_key") or "").strip() or None
        if entity_type and entity_key:
            if entity_type not in FIELD_MAP:
                return None, None
            return entity_type, entity_key

        if ctx.event.aggregate_host_name:
            return "host", ctx.event.aggregate_host_name
        if ctx.event.aggregate_user_name:
            return "user", ctx.event.aggregate_user_name
        for alert in ctx.alerts:
            if alert.src_ip:
                return "ip", alert.src_ip
            if alert.host_name:
                return "host", alert.host_name
            if alert.user_name:
                return "user", alert.user_name
        return entity_type, entity_key
