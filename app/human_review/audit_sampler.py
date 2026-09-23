"""Audit sample generation for ring-outside quality checks."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AlertStatus, AuditSampleReason, RouteDecision
from app.human_review.config import load_human_review_config
from app.models.human_review import AuditSample
from app.models.ingestion import Alert
from app.models.triage import TriageResult

logger = logging.getLogger(__name__)


@dataclass
class AuditSampleRunResult:
    created: int = 0
    skipped_disabled: bool = False
    errors: list[str] = field(default_factory=list)


class AuditSampleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(self, *, limit: int = 50) -> AuditSampleRunResult:
        result = AuditSampleRunResult()
        config = await load_human_review_config(self.session)
        if not config.audit_sample_enabled:
            result.skipped_disabled = True
            return result

        sampled_alerts = select(AuditSample.alert_id).where(AuditSample.alert_id.is_not(None))
        stmt = (
            select(Alert, TriageResult)
            .join(TriageResult, TriageResult.alert_id == Alert.id)
            .where(
                Alert.status == AlertStatus.ARCHIVED,
                TriageResult.route_decision == RouteDecision.SAMPLE_AUDIT,
                Alert.id.not_in(sampled_alerts),
            )
            .limit(limit)
        )
        rows = await self.session.execute(stmt)
        for alert, _triage in rows.all():
            try:
                self.session.add(
                    AuditSample(
                        alert_id=alert.id,
                        sample_reason=AuditSampleReason.LOW_RISK_RANDOM,
                    )
                )
                result.created += 1
            except Exception as exc:
                result.errors.append(f"{alert.id}: {exc}")
                logger.exception("Failed to create audit sample for alert=%s", alert.id)

        if result.created:
            await self.session.commit()
        return result

    async def submit_review(
        self,
        sample_id,
        *,
        review_verdict,
        is_correct: bool | None,
        feedback: str | None = None,
    ) -> bool:
        from app.core.datetime_utils import utc_now

        sample = await self.session.get(AuditSample, sample_id)
        if sample is None:
            return False
        sample.review_verdict = review_verdict
        sample.is_correct = is_correct
        sample.feedback = feedback
        sample.reviewed_at = utc_now()
        await self.session.commit()
        return True
