"""Event aggregation orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.datetime_utils import as_naive_utc, utc_now

from app.aggregation.config import AggregationConfig, load_aggregation_config
from app.aggregation.key import normalize_dimensions
from app.aggregation.lock import aggregation_lock
from app.aggregation.priority import route_priority
from app.aggregation.title import build_event_title
from app.db.enums import ActorType, AlertStatus, EventStatus, RouteDecision
from app.models.ingestion import Alert
from app.models.investigation import Event, EventAlert
from app.models.system import AuditLog
from app.models.triage import TriageResult

logger = logging.getLogger(__name__)

QUEUE_ROUTES = {
    RouteDecision.QUEUE_DEEP_REVIEW,
    RouteDecision.QUEUE_UNCERTAIN,
}


@dataclass
class AggregationRunResult:
    processed: int = 0
    events_created: int = 0
    events_merged: int = 0
    skipped: int = 0
    skipped_lock: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class PendingAlert:
    alert: Alert
    triage: TriageResult


class AggregationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(self, *, limit: int | None = None, use_lock: bool = True) -> AggregationRunResult:
        result = AggregationRunResult()

        async def _execute() -> AggregationRunResult:
            config = await load_aggregation_config(self.session)
            batch_limit = limit or config.batch_size
            pending = await self._fetch_pending(batch_limit)
            for item in pending:
                try:
                    created = await self._aggregate_one(item, config)
                    await self.session.commit()
                    result.processed += 1
                    if created:
                        result.events_created += 1
                    else:
                        result.events_merged += 1
                except Exception as exc:
                    await self.session.rollback()
                    result.errors.append(f"{item.alert.id}: {exc}")
                    logger.exception("Aggregation failed for alert=%s", item.alert.id)

            if result.processed:
                self.session.add(
                    AuditLog(
                        actor_type=ActorType.SYSTEM,
                        action="aggregation.batch_completed",
                        resource_type="aggregation",
                        resource_id="global",
                        detail={
                            "processed": result.processed,
                            "events_created": result.events_created,
                            "events_merged": result.events_merged,
                            "errors": len(result.errors),
                        },
                    )
                )
                await self.session.commit()
            return result

        if use_lock:
            async with aggregation_lock() as acquired:
                if not acquired:
                    result.skipped_lock = True
                    return result
                return await _execute()
        return await _execute()

    async def get_stats(self) -> dict:
        pending_count = await self.session.execute(
            select(func.count())
            .select_from(Alert)
            .join(TriageResult, TriageResult.alert_id == Alert.id)
            .outerjoin(EventAlert, EventAlert.alert_id == Alert.id)
            .where(
                Alert.status == AlertStatus.TRIAGED,
                TriageResult.route_decision.in_(QUEUE_ROUTES),
                EventAlert.id.is_(None),
            )
        )
        events_today = await self.session.execute(
            select(func.count())
            .select_from(Event)
            .where(Event.created_at >= utc_now().replace(hour=0, minute=0, second=0, microsecond=0))
        )
        avg_alerts = await self.session.execute(select(func.avg(Event.alert_count)))
        return {
            "pending_alerts": int(pending_count.scalar_one() or 0),
            "events_created_today": int(events_today.scalar_one() or 0),
            "avg_alerts_per_event": float(avg_alerts.scalar_one() or 0.0),
        }

    async def get_event_detail(self, event_id: UUID) -> dict | None:
        result = await self.session.execute(
            select(Event)
            .options(selectinload(Event.alert_links).selectinload(EventAlert.alert))
            .where(Event.id == event_id)
        )
        event = result.scalar_one_or_none()
        if event is None:
            return None

        alerts_payload = []
        for link in event.alert_links:
            alert = link.alert
            alerts_payload.append(
                {
                    "alert_id": str(alert.id),
                    "source_alert_id": alert.source_alert_id,
                    "severity": alert.severity,
                    "occurred_at": alert.occurred_at.isoformat(),
                    "rule_name": alert.rule_name,
                }
            )

        return {
            "id": str(event.id),
            "event_key": event.event_key,
            "title": event.title,
            "status": event.status.value,
            "queue_priority": event.queue_priority,
            "risk_score": event.risk_score,
            "alert_count": event.alert_count,
            "first_alert_at": event.first_alert_at.isoformat() if event.first_alert_at else None,
            "last_alert_at": event.last_alert_at.isoformat() if event.last_alert_at else None,
            "aggregate_host_name": event.aggregate_host_name,
            "aggregate_user_name": event.aggregate_user_name,
            "aggregate_category": event.aggregate_category,
            "aggregate_window_start": event.aggregate_window_start.isoformat()
            if event.aggregate_window_start
            else None,
            "alerts": alerts_payload,
        }

    async def _aggregate_one(self, item: PendingAlert, config: AggregationConfig) -> bool:
        """Returns True if a new event was created."""
        alert = item.alert
        triage = item.triage
        now = utc_now()

        dims = normalize_dimensions(
            host_name=alert.host_name,
            user_name=alert.user_name,
            alert_category=alert.alert_category,
            occurred_at=as_naive_utc(alert.occurred_at),
            window_hours=config.window_hours,
            unknown_host_sentinel=config.unknown_host_sentinel,
            unknown_user_sentinel=config.unknown_user_sentinel,
        )

        event = await self._find_merge_target(dims.event_key)
        created = event is None
        if created:
            event = Event(
                event_key=dims.event_key,
                primary_category=alert.alert_category,
                aggregate_host_name=alert.host_name,
                aggregate_user_name=alert.user_name,
                aggregate_category=alert.alert_category,
                aggregate_window_start=dims.window_start,
                status=EventStatus.PENDING_REVIEW,
                alert_count=0,
                risk_score=0.0,
                queue_priority=0,
            )
            self.session.add(event)
            await self.session.flush()

        max_severity = await self._max_severity_for_event(event.id, alert.severity)

        self.session.add(
            EventAlert(
                event_id=event.id,
                alert_id=alert.id,
                added_at=now,
            )
        )

        alert.status = AlertStatus.EVENT_LINKED
        self._update_event_stats(event, alert, triage, max_severity=max_severity)
        return created

    async def _max_severity_for_event(self, event_id: UUID, current_severity: int) -> int:
        result = await self.session.execute(
            select(func.max(Alert.severity))
            .join(EventAlert, EventAlert.alert_id == Alert.id)
            .where(EventAlert.event_id == event_id)
        )
        existing = result.scalar_one()
        if existing is None:
            return current_severity
        return max(int(existing), current_severity)

    async def _find_merge_target(self, event_key: str) -> Event | None:
        result = await self.session.execute(
            select(Event)
            .where(
                Event.event_key == event_key,
                Event.status == EventStatus.PENDING_REVIEW,
            )
            .order_by(Event.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _update_event_stats(
        event: Event,
        alert: Alert,
        triage: TriageResult,
        *,
        max_severity: int,
    ) -> None:
        event.alert_count += 1
        event.first_alert_at = (
            alert.occurred_at
            if event.first_alert_at is None
            else min(event.first_alert_at, alert.occurred_at)
        )
        event.last_alert_at = (
            alert.occurred_at
            if event.last_alert_at is None
            else max(event.last_alert_at, alert.occurred_at)
        )
        event.risk_score = max(event.risk_score, triage.rule_score)
        event.queue_priority = max(event.queue_priority, route_priority(triage.route_decision))

        event.title = build_event_title(
            category=event.aggregate_category,
            host_name=event.aggregate_host_name,
            user_name=event.aggregate_user_name,
            alert_count=event.alert_count,
            max_severity=max_severity,
        )

    async def _fetch_pending(self, limit: int) -> list[PendingAlert]:
        stmt = (
            select(Alert, TriageResult)
            .join(TriageResult, TriageResult.alert_id == Alert.id)
            .outerjoin(EventAlert, EventAlert.alert_id == Alert.id)
            .where(
                Alert.status == AlertStatus.TRIAGED,
                TriageResult.route_decision.in_(QUEUE_ROUTES),
                EventAlert.id.is_(None),
            )
            .order_by(Alert.occurred_at.asc())
            .limit(limit)
        )
        rows = await self.session.execute(stmt)
        return [PendingAlert(alert=alert, triage=triage) for alert, triage in rows.all()]
