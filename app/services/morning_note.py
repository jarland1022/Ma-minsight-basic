"""Build overnight Morning Note digest from live console data."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.semantics import active_security_verdict
from app.core.datetime_utils import as_naive_utc, utc_now
from app.db.enums import (
    AlertStatus,
    EventStatus,
    HumanReviewStatus,
    InvestigationStatus,
    InvestigationVerdict,
    RouteDecision,
)
from app.models.human_review import HumanReviewRequest
from app.models.ingestion import Alert
from app.models.investigation import Event, Investigation, InvestigationConclusion
from app.models.triage import TriageResult

ARCHIVE_ROUTES = {
    RouteDecision.ARCHIVE_LOW_RISK,
    RouteDecision.ARCHIVE_WHITELIST,
    RouteDecision.ARCHIVE_DEDUP,
    RouteDecision.SAMPLE_AUDIT,
}

ROUTE_LABELS = {
    RouteDecision.ARCHIVE_LOW_RISK.value: "low_risk",
    RouteDecision.ARCHIVE_WHITELIST.value: "whitelist",
    RouteDecision.ARCHIVE_DEDUP.value: "dedup",
    RouteDecision.SAMPLE_AUDIT.value: "sample_audit",
}


def _resolve_window(
    *,
    hours: float | None,
    since: datetime | None,
    until: datetime | None,
) -> tuple[datetime, datetime]:
    end = as_naive_utc(until) if until else utc_now()
    if since:
        start = as_naive_utc(since)
    else:
        h = hours if hours is not None and hours > 0 else 15.0
        start = end - timedelta(hours=h)
    if start >= end:
        start = end - timedelta(hours=1)
    return start, end


def _verdict_tag(verdict: str | None) -> str:
    if verdict == InvestigationVerdict.ATTACK_CONFIRMED.value:
        return "danger"
    if verdict == InvestigationVerdict.LIKELY_FALSE_POSITIVE.value:
        return "ok"
    return "warn"


async def build_morning_note(
    session: AsyncSession,
    *,
    hours: float | None = 15.0,
    since: datetime | None = None,
    until: datetime | None = None,
    timezone_label: str = "UTC",
    worth_limit: int = 5,
) -> dict[str, Any]:
    window_start, window_end = _resolve_window(hours=hours, since=since, until=until)

    ingested = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Alert)
                .where(
                    Alert.ingested_at >= window_start,
                    Alert.ingested_at < window_end,
                )
            )
        ).scalar_one()
    )

    archived = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Alert)
                .where(
                    Alert.ingested_at >= window_start,
                    Alert.ingested_at < window_end,
                    Alert.status == AlertStatus.ARCHIVED,
                )
            )
        ).scalar_one()
    )

    archive_rows = (
        await session.execute(
            select(TriageResult.route_decision, func.count())
            .join(Alert, Alert.id == TriageResult.alert_id)
            .where(
                Alert.ingested_at >= window_start,
                Alert.ingested_at < window_end,
                TriageResult.route_decision.in_(tuple(ARCHIVE_ROUTES)),
            )
            .group_by(TriageResult.route_decision)
        )
    ).all()
    archive_breakdown = {
        ROUTE_LABELS.get(str(route), str(route)): int(cnt) for route, cnt in archive_rows
    }

    queued = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Event)
                .where(
                    Event.status.in_(
                        (EventStatus.PENDING_REVIEW, EventStatus.INVESTIGATING)
                    ),
                    Event.created_at >= window_start,
                    Event.created_at < window_end,
                )
            )
        ).scalar_one()
    )

    needs_reply = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Event)
                .where(Event.status == EventStatus.HUMAN_PENDING)
            )
        ).scalar_one()
    )

    # Cases worth opening: open / human_pending / recently concluded with high signal
    worth_stmt = (
        select(Event)
        .where(
            Event.status.in_(
                (
                    EventStatus.PENDING_REVIEW,
                    EventStatus.INVESTIGATING,
                    EventStatus.HUMAN_PENDING,
                    EventStatus.CONCLUDED,
                )
            ),
            Event.last_alert_at.is_not(None),
            Event.last_alert_at >= window_start,
            Event.last_alert_at < window_end,
        )
        .order_by(Event.queue_priority.desc(), Event.risk_score.desc())
        .limit(max(worth_limit, 1))
        .options(
            selectinload(Event.investigations)
            .selectinload(Investigation.conclusion),
            selectinload(Event.human_review_requests),
        )
    )
    worth_events = list((await session.execute(worth_stmt)).scalars().unique().all())

    cases: list[dict[str, Any]] = []
    for ev in worth_events:
        invs = sorted(
            ev.investigations or [],
            key=lambda i: i.created_at or datetime.min,
            reverse=True,
        )
        latest = invs[0] if invs else None
        conclusion = latest.conclusion if latest else None
        stored = conclusion.verdict.value if conclusion and conclusion.verdict else None
        invalidated = bool(conclusion.invalidated_as_ops_failure) if conclusion else False
        verdict = active_security_verdict(
            investigation_status=latest.status.value if latest and latest.status else None,
            verdict=stored,
            invalidated_as_ops_failure=invalidated,
        )
        # Prefer unanswered / still-open human questions
        pending_q = next(
            (
                r
                for r in (ev.human_review_requests or [])
                if r.status == HumanReviewStatus.SENT
            ),
            None,
        )
        if pending_q is None and conclusion and conclusion.human_query:
            human_q = conclusion.human_query
        else:
            human_q = pending_q.question if pending_q else None

        cases.append(
            {
                "event_id": str(ev.id),
                "title": ev.title or ev.event_key,
                "status": ev.status.value if ev.status else None,
                "risk_score": ev.risk_score,
                "queue_priority": ev.queue_priority,
                "alert_count": ev.alert_count,
                "host": ev.aggregate_host_name,
                "user": ev.aggregate_user_name,
                "category": ev.aggregate_category or ev.primary_category,
                "verdict": verdict,
                "verdict_tag": _verdict_tag(verdict),
                "confidence": conclusion.confidence if conclusion else None,
                "evidence_closure_score": (
                    conclusion.evidence_closure_score if conclusion else None
                ),
                "reasoning": (conclusion.reasoning[:400] if conclusion and conclusion.reasoning else None),
                "recommended_action": (
                    conclusion.recommended_action if conclusion else None
                ),
                "human_question": human_q,
                "investigation_id": str(latest.id) if latest else None,
                "investigation_status": (
                    latest.status.value if latest and latest.status else None
                ),
            }
        )

    open_reviews = (
        await session.execute(
            select(HumanReviewRequest)
            .where(HumanReviewRequest.status == HumanReviewStatus.SENT)
            .order_by(HumanReviewRequest.created_at.desc())
            .limit(10)
            .options(selectinload(HumanReviewRequest.event))
        )
    ).scalars().all()

    human_items = []
    for req in open_reviews:
        human_items.append(
            {
                "request_id": str(req.id),
                "event_id": str(req.event_id),
                "event_title": (req.event.title if req.event else None) or str(req.event_id),
                "question": req.question,
                "sent_at": req.sent_at.isoformat() if req.sent_at else None,
            }
        )

    return {
        "generated_at": utc_now().isoformat(timespec="seconds") + "Z",
        "timezone_label": timezone_label,
        "window": {
            "start": window_start.isoformat(timespec="seconds") + "Z",
            "end": window_end.isoformat(timespec="seconds") + "Z",
            "hours": round((window_end - window_start).total_seconds() / 3600, 2),
        },
        "snapshot": {
            "ingested_alerts": ingested,
            "auto_archived": archived,
            "queued_investigating": queued,
            "worth_opening": len(cases),
            "needs_reply": needs_reply,
            "archive_breakdown": archive_breakdown,
        },
        "cases": cases,
        "human_reviews": human_items,
        "boundaries": [
            "No SIEM admin login required for this digest",
            "No firewall / WAF policy push",
            "No host isolation",
            "Confirmations and blocking decisions stay with you",
        ],
    }
