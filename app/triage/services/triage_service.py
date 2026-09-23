"""Triage batch orchestration service."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import ActorType, AlertStatus
from app.models.ingestion import Alert, DataSource
from app.models.system import AuditLog
from app.models.triage import TriageResult
from app.triage.config import TriageConfig, load_triage_config
from app.triage.lock import triage_lock
from app.triage.pipeline import TriagePipeline
from app.triage.schemas.context import AlertSnapshot, TriageContext

logger = logging.getLogger(__name__)


@dataclass
class TriageRunResult:
    processed: int = 0
    skipped: int = 0
    skipped_lock: bool = False
    errors: list[str] = field(default_factory=list)


class TriageService:
    def __init__(self, session: AsyncSession, pipeline: TriagePipeline | None = None) -> None:
        self.session = session
        self.pipeline = pipeline or TriagePipeline()

    async def run(self, *, limit: int | None = None, use_lock: bool = True) -> TriageRunResult:
        result = TriageRunResult()

        async def _execute() -> TriageRunResult:
            config = await load_triage_config(self.session)
            config.llm_assist_calls_this_run = 0
            batch_limit = limit or config.batch_size
            alerts = await self._fetch_new_alerts(batch_limit)
            for alert, source_name in alerts:
                try:
                    ctx = TriageContext(
                        alert=AlertSnapshot(
                            id=alert.id,
                            data_source_id=alert.data_source_id,
                            data_source_name=source_name,
                            source_alert_id=alert.source_alert_id,
                            fingerprint=alert.fingerprint,
                            rule_id=alert.rule_id,
                            rule_name=alert.rule_name,
                            severity=alert.severity,
                            occurred_at=alert.occurred_at,
                            src_ip=str(alert.src_ip) if alert.src_ip else None,
                            dst_ip=str(alert.dst_ip) if alert.dst_ip else None,
                            user_name=alert.user_name,
                            host_name=alert.host_name,
                            file_hash=alert.file_hash,
                            alert_category=alert.alert_category,
                            normalized_fields=alert.normalized_fields,
                            raw_data=alert.raw_data,
                        )
                    )
                    await self.pipeline.run(ctx, self.session, config)
                    await self.session.commit()
                    result.processed += 1
                except Exception as exc:
                    await self.session.rollback()
                    result.errors.append(f"{alert.id}: {exc}")
                    logger.exception("Triage failed for alert=%s", alert.id)

            if result.processed:
                self.session.add(
                    AuditLog(
                        actor_type=ActorType.SYSTEM,
                        action="triage.batch_completed",
                        resource_type="triage",
                        resource_id="global",
                        detail={
                            "processed": result.processed,
                            "skipped": result.skipped,
                            "errors": len(result.errors),
                        },
                    )
                )
                await self.session.commit()
            return result

        if use_lock:
            async with triage_lock() as acquired:
                if not acquired:
                    result.skipped_lock = True
                    return result
                return await _execute()
        return await _execute()

    async def get_stats(self) -> dict:
        from sqlalchemy import func

        from app.db.enums import RouteDecision

        stats: dict[str, int] = {}
        for route in RouteDecision:
            count_result = await self.session.execute(
                select(func.count())
                .select_from(TriageResult)
                .where(TriageResult.route_decision == route)
            )
            stats[route.value] = int(count_result.scalar_one() or 0)
        return stats

    async def get_alert_triage(self, alert_id: UUID) -> dict | None:
        alert = await self.session.get(Alert, alert_id)
        if alert is None:
            return None
        triage = await self.session.execute(
            select(TriageResult).where(TriageResult.alert_id == alert_id)
        )
        triage_row = triage.scalar_one_or_none()
        return {
            "alert_id": str(alert.id),
            "status": alert.status.value,
            "fingerprint": alert.fingerprint,
            "triage": None
            if triage_row is None
            else {
                "route_decision": triage_row.route_decision.value,
                "rule_score": triage_row.rule_score,
                "profile_hint_score": triage_row.profile_hint_score,
                "whitelist_rule_id": str(triage_row.whitelist_rule_id)
                if triage_row.whitelist_rule_id
                else None,
                "route_reason": triage_row.route_reason,
                "triaged_at": triage_row.triaged_at.isoformat(),
            },
        }

    async def _fetch_new_alerts(self, limit: int) -> list[tuple[Alert, str]]:
        stmt = (
            select(Alert, DataSource.name)
            .join(DataSource, Alert.data_source_id == DataSource.id)
            .outerjoin(TriageResult, TriageResult.alert_id == Alert.id)
            .where(Alert.status == AlertStatus.NEW, TriageResult.id.is_(None))
            .order_by(Alert.occurred_at.asc())
            .limit(limit)
        )
        rows = await self.session.execute(stmt)
        return [(alert, name) for alert, name in rows.all()]
