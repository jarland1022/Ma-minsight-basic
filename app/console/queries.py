"""Console query helpers for dashboard and event views."""

from __future__ import annotations

from typing import Literal

from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.budget import budget_remaining, get_daily_count
from app.agent.config import load_investigation_config
from app.core.datetime_utils import utc_now
from datetime import datetime, timedelta
from app.services.system_config import get_config_bool, get_config_int
from app.db.enums import (
    AlertStatus,
    DispositionSimulationApprovalStatus,
    DispositionStatus,
    EventStatus,
    HumanReviewStatus,
    InvestigationStatus,
    ProfileUpdateStatus,
    WhitelistCandidateStatus,
)
from app.models.defense_assets import (
    DispositionRecord,
    DispositionSimulation,
    JudgmentCase,
    ProfileUpdateSuggestion,
)
from app.models.cache_eval import RegressionTestRun
from app.eval.health_check.runner import HealthCheckRunner
from app.human_review.stale import is_system_error_human_query
from app.models.human_review import HumanReviewRequest
from app.models.ingestion import Alert
from app.models.investigation import Event, EventAlert, Investigation, InvestigationAudit
from app.models.system import AuditLog
from app.models.triage import TriageResult, WhitelistCandidate


async def _schema_capabilities(session: AsyncSession) -> frozenset[str]:
    caps: set[str] = set()
    tables = {
        row[0]
        for row in (
            await session.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN (
                        'investigation_audits',
                        'disposition_simulations',
                        'events',
                        'investigations'
                      )
                    """
                )
            )
        ).all()
    }
    if "investigation_audits" in tables:
        caps.add("investigation_audits")
    if "disposition_simulations" in tables:
        caps.add("disposition_simulations")
    if "events" in tables:
        cols = {
            row[0]
            for row in (
                await session.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'events'
                          AND column_name = 'related_event_ids'
                        """
                    )
                )
            ).all()
        }
        if cols:
            caps.add("related_event_ids")
    if "investigations" in tables:
        cols = {
            row[0]
            for row in (
                await session.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'investigations'
                          AND column_name IN ('closure_retry_count', 'token_input')
                        """
                    )
                )
            ).all()
        }
        if "closure_retry_count" in cols:
            caps.add("investigations_phase2")
        if "token_input" in cols:
            caps.add("investigations_metrics")
    return frozenset(caps)


async def dashboard_summary(session: AsyncSession) -> dict:
    caps = await _schema_capabilities(session)
    inv_config = await load_investigation_config(session)
    remaining = await budget_remaining(inv_config.daily_event_budget)
    today_count = await get_daily_count()

    async def _count(model, *filters):
        stmt = select(func.count()).select_from(model)
        for f in filters:
            stmt = stmt.where(f)
        return int((await session.execute(stmt)).scalar_one() or 0)

    alerts_new = await _count(Alert, Alert.status == AlertStatus.NEW)
    alerts_triaged = await _count(Alert, Alert.status == AlertStatus.TRIAGED)
    alerts_archived = await _count(Alert, Alert.status == AlertStatus.ARCHIVED)

    events_by_status = {}
    for st in EventStatus:
        events_by_status[st.value] = await _count(Event, Event.status == st)

    human_sent = await _count(HumanReviewRequest, HumanReviewRequest.status == HumanReviewStatus.SENT)
    human_answered = await _count(
        HumanReviewRequest, HumanReviewRequest.status == HumanReviewStatus.ANSWERED
    )

    judgment_cases = await _count(JudgmentCase)
    disposition_suggested = await _count(
        DispositionRecord, DispositionRecord.status == DispositionStatus.SUGGESTED
    )
    simulation_draft = 0
    if "disposition_simulations" in caps:
        simulation_draft = await _count(
            DispositionSimulation,
            DispositionSimulation.approval_status == DispositionSimulationApprovalStatus.DRAFT,
        )

    pipeline_last_run = {}
    for action, key in [
        ("ingestion.batch_completed", "ingestion"),
        ("triage.batch_completed", "triage"),
        ("aggregation.batch_completed", "aggregation"),
        ("investigation.batch_completed", "investigation"),
        ("human_review.batch_completed", "human_review"),
        ("defense_assets.batch_completed", "defense_assets"),
    ]:
        result = await session.execute(
            select(AuditLog.created_at)
            .where(AuditLog.action == action)
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        ts = result.scalar_one_or_none()
        pipeline_last_run[key] = ts.isoformat() if ts else None

    last_regression = await session.execute(
        select(RegressionTestRun).order_by(RegressionTestRun.run_at.desc()).limit(1)
    )
    reg_run = last_regression.scalar_one_or_none()
    last_hc = await HealthCheckRunner(session).latest_summary()

    eval_block = {
        "last_regression": None
        if reg_run is None
        else {
            "run_id": str(reg_run.id),
            "passed": reg_run.passed,
            "failed": reg_run.failed,
            "total": reg_run.total,
            "run_at": reg_run.run_at.isoformat(),
            "healthy": reg_run.failed == 0,
        },
        "last_health_check": last_hc,
        "healthy": (reg_run is None or reg_run.failed == 0)
        and (last_hc is None or last_hc.get("passed", True)),
    }

    metrics_enabled = await get_config_bool(session, "investigation.metrics_enabled", True)
    inv_cost: dict = {}
    if metrics_enabled and "investigations_metrics" in caps:
        today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        cost_row = await session.execute(
            select(
                func.count(Investigation.id),
                func.coalesce(func.avg(Investigation.token_input + Investigation.token_output), 0),
                func.coalesce(func.avg(Investigation.skill_call_count), 0),
                func.coalesce(
                    func.avg(
                        func.extract("epoch", Investigation.finished_at - Investigation.started_at)
                    ),
                    0,
                ),
            ).where(
                Investigation.started_at >= today_start,
                Investigation.finished_at.isnot(None),
            )
        )
        count, avg_tokens, avg_skills, avg_duration_sec = cost_row.one()
        p95_row = await session.execute(
            select(
                func.percentile_cont(0.95).within_group(
                    func.extract("epoch", Investigation.finished_at - Investigation.started_at)
                )
            ).where(
                Investigation.started_at >= today_start,
                Investigation.finished_at.isnot(None),
            )
        )
        p95_duration = p95_row.scalar_one_or_none()
        inv_cost = {
            "today_completed": int(count or 0),
            "avg_tokens_per_event": round(float(avg_tokens or 0), 1),
            "avg_skill_calls_per_event": round(float(avg_skills or 0), 1),
            "avg_duration_seconds": round(float(avg_duration_sec or 0), 1),
            "p95_duration_seconds": round(float(p95_duration or 0), 1),
            "target_tokens_per_event": await get_config_int(
                session, "investigation.target_tokens_per_event", 10000
            ),
        }

    correlated_count = 0
    if "related_event_ids" in caps:
        correlated_count = int(
            (
                await session.execute(
                    select(func.count()).select_from(Event).where(Event.related_event_ids.isnot(None))
                )
            ).scalar_one()
            or 0
        )

    supervisor_enabled = await get_config_bool(session, "investigation.supervisor_enabled", True)
    supervisor_block: dict = {}
    if supervisor_enabled and "investigation_audits" in caps and "investigations_phase2" in caps:
        week_start = utc_now() - timedelta(days=7)
        audit_row = await session.execute(
            select(
                func.count(InvestigationAudit.id),
                func.count(InvestigationAudit.id).filter(InvestigationAudit.passed.is_(False)),
            ).where(InvestigationAudit.created_at >= week_start)
        )
        total_audits, failed_audits = audit_row.one()
        total_audits = int(total_audits or 0)
        failed_audits = int(failed_audits or 0)
        supervisor_block = {
            "audit_total_7d": total_audits,
            "audit_failed_7d": failed_audits,
            "audit_failure_rate_7d": round(failed_audits / total_audits, 3) if total_audits else 0.0,
        }

    return {
        "alerts": {"new": alerts_new, "triaged": alerts_triaged, "archived": alerts_archived},
        "events": events_by_status,
        "correlation": {
            "events_with_related": correlated_count,
        },
        "investigations": {
            "today_count": today_count,
            "daily_budget": inv_config.daily_event_budget,
            "budget_remaining": remaining,
            **inv_cost,
        },
        "supervisor": supervisor_block,
        "human_review": {"sent": human_sent, "answered": human_answered},
        "defense_assets": {
            "judgment_cases": judgment_cases,
            "disposition_suggested": disposition_suggested,
            "simulation_draft": simulation_draft,
        },
        "pipeline_last_run": pipeline_last_run,
        "eval": eval_block,
    }


async def _active_human_review_by_event_ids(
    session: AsyncSession,
    event_ids: list[UUID],
) -> dict[UUID, tuple[datetime | None, str]]:
    """Latest SENT human-review request per event (sent_at, question)."""
    if not event_ids:
        return {}
    result = await session.execute(
        select(HumanReviewRequest)
        .where(
            HumanReviewRequest.event_id.in_(event_ids),
            HumanReviewRequest.status == HumanReviewStatus.SENT,
        )
        .order_by(HumanReviewRequest.sent_at.desc().nulls_last())
    )
    out: dict[UUID, tuple[datetime | None, str]] = {}
    for req in result.scalars().all():
        if req.event_id not in out:
            out[req.event_id] = (req.sent_at, req.question)
    return out


async def list_events(
    session: AsyncSession,
    *,
    status: EventStatus | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: Literal[
        "concluded_at",
        "investigation_finished_at",
        "human_review_sent_at",
        "risk_score",
        "queue_priority",
        "last_alert_at",
    ]
    | None = None,
    sort_order: Literal["asc", "desc"] = "desc",
) -> dict:
    count_stmt = select(func.count()).select_from(Event)
    if status is not None:
        count_stmt = count_stmt.where(Event.status == status)
    if category:
        count_stmt = count_stmt.where(Event.primary_category == category)

    total = int((await session.execute(count_stmt)).scalar_one() or 0)

    latest_inv = (
        select(
            Investigation.event_id.label("event_id"),
            func.max(Investigation.finished_at).label("investigation_finished_at"),
        )
        .where(Investigation.finished_at.isnot(None))
        .group_by(Investigation.event_id)
        .subquery()
    )
    active_hr = (
        select(
            HumanReviewRequest.event_id.label("event_id"),
            func.max(HumanReviewRequest.sent_at).label("human_review_sent_at"),
        )
        .where(HumanReviewRequest.status == HumanReviewStatus.SENT)
        .group_by(HumanReviewRequest.event_id)
        .subquery()
    )
    stmt = (
        select(Event, latest_inv.c.investigation_finished_at, active_hr.c.human_review_sent_at)
        .outerjoin(latest_inv, Event.id == latest_inv.c.event_id)
        .outerjoin(active_hr, Event.id == active_hr.c.event_id)
    )
    if status is not None:
        stmt = stmt.where(Event.status == status)
    if category:
        stmt = stmt.where(Event.primary_category == category)

    if sort_by is None and status in {EventStatus.CONCLUDED, EventStatus.CLOSED}:
        sort_by = "concluded_at"
        sort_order = "desc"
    if sort_by is None and status == EventStatus.HUMAN_PENDING:
        sort_by = "human_review_sent_at"
        sort_order = "desc"

    if sort_by == "concluded_at":
        sort_by = "investigation_finished_at"

    order_col = {
        "investigation_finished_at": latest_inv.c.investigation_finished_at,
        "human_review_sent_at": active_hr.c.human_review_sent_at,
        "risk_score": Event.risk_score,
        "queue_priority": Event.queue_priority,
        "last_alert_at": Event.last_alert_at,
    }.get(sort_by or "")

    if sort_by == "human_review_sent_at":
        primary = (
            active_hr.c.human_review_sent_at.asc()
            if sort_order == "asc"
            else active_hr.c.human_review_sent_at.desc()
        )
        secondary = latest_inv.c.investigation_finished_at.desc().nulls_last()
        stmt = stmt.order_by(primary.nulls_last(), secondary)
    elif order_col is not None:
        ordering = order_col.asc() if sort_order == "asc" else order_col.desc()
        nulls_last = sort_by in {"investigation_finished_at", "human_review_sent_at", "last_alert_at"}
        stmt = stmt.order_by(ordering.nulls_last() if nulls_last else ordering)
    else:
        stmt = stmt.order_by(
            Event.queue_priority.desc(),
            Event.risk_score.desc(),
            Event.last_alert_at.asc(),
        )
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(stmt)
    rows = result.all()
    event_ids = [e.id for e, _, _ in rows]
    hr_details = await _active_human_review_by_event_ids(session, event_ids)

    items = []
    for e, investigation_finished_at, human_review_sent_at in rows:
        _, question = hr_details.get(e.id, (None, ""))
        question_preview = question.strip()
        if len(question_preview) > 120:
            question_preview = f"{question_preview[:117]}..."
        items.append(
            {
                "id": str(e.id),
                "title": e.title,
                "status": e.status.value,
                "primary_category": e.primary_category,
                "queue_priority": e.queue_priority,
                "risk_score": e.risk_score,
                "alert_count": e.alert_count,
                "last_alert_at": e.last_alert_at.isoformat() if e.last_alert_at else None,
                "concluded_at": investigation_finished_at.isoformat() if investigation_finished_at else None,
                "investigation_finished_at": investigation_finished_at.isoformat()
                if investigation_finished_at
                else None,
                "human_review_sent_at": human_review_sent_at.isoformat() if human_review_sent_at else None,
                "human_review_question": question_preview or None,
                "human_review_dispatched": human_review_sent_at is not None,
                "human_review_is_system_error": is_system_error_human_query(question),
                "aggregate_host_name": e.aggregate_host_name,
                "aggregate_user_name": e.aggregate_user_name,
            }
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_event_console_detail(session: AsyncSession, event_id: UUID) -> dict | None:
    from app.aggregation.services.aggregation_service import AggregationService

    base = await AggregationService(session).get_event_detail(event_id)
    if base is None:
        return None

    inv_result = await session.execute(
        select(Investigation)
        .options(
            selectinload(Investigation.conclusion),
            selectinload(Investigation.audits),
            selectinload(Investigation.disposition_simulations),
            selectinload(Investigation.sop),
        )
        .where(Investigation.event_id == event_id)
        .order_by(Investigation.started_at.desc())
    )
    investigations = []
    inv_ids: list[UUID] = []
    for inv in inv_result.scalars().all():
        inv_ids.append(inv.id)
        investigations.append(
            {
                "id": str(inv.id),
                "status": inv.status.value,
                "started_at": inv.started_at.isoformat(),
                "finished_at": inv.finished_at.isoformat() if inv.finished_at else None,
                "closure_retry_count": inv.closure_retry_count,
                "hypothesis_template": inv.sop.hypothesis_template if inv.sop else None,
                "conclusion": None
                if inv.conclusion is None
                else {
                    "verdict": inv.conclusion.verdict.value,
                    "confidence": inv.conclusion.confidence,
                    "reasoning": inv.conclusion.reasoning,
                    "human_query": inv.conclusion.human_query,
                    "recommended_action": inv.conclusion.recommended_action,
                    "evidence_closure_score": inv.conclusion.evidence_closure_score,
                    "refutation_coverage": inv.conclusion.refutation_coverage,
                    "closure_passed": inv.conclusion.closure_passed,
                    "closure_checks": inv.conclusion.closure_checks,
                    "hypotheses_evaluated": inv.conclusion.hypotheses_evaluated,
                    "refutation_summary": inv.conclusion.refutation_summary,
                },
                "supervisor_audits": [
                    {
                        "id": str(a.id),
                        "audit_type": a.audit_type,
                        "passed": a.passed,
                        "findings": a.findings,
                        "supervisor_model": a.supervisor_model,
                        "created_at": a.created_at.isoformat(),
                    }
                    for a in sorted(inv.audits, key=lambda x: x.created_at)
                ],
                "disposition_simulations": [
                    _simulation_summary_row(sim) for sim in inv.disposition_simulations
                ],
            }
        )

    hr_result = await session.execute(
        select(HumanReviewRequest)
        .where(HumanReviewRequest.event_id == event_id)
        .order_by(HumanReviewRequest.created_at.desc())
    )
    human_reviews = [
        {
            "id": str(r.id),
            "status": r.status.value,
            "question": r.question,
            "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            "answered_at": r.answered_at.isoformat() if r.answered_at else None,
        }
        for r in hr_result.scalars().all()
    ]

    dispositions = []
    if inv_ids:
        disp_result = await session.execute(
            select(DispositionRecord)
            .where(DispositionRecord.investigation_id.in_(inv_ids))
            .order_by(DispositionRecord.created_at.desc())
        )
        dispositions = [
            {
                "id": str(d.id),
                "investigation_id": str(d.investigation_id),
                "suggested_action": d.suggested_action,
                "status": d.status.value,
                "confirmed_action": d.confirmed_action,
            }
            for d in disp_result.scalars().all()
        ]

    from app.geoip.enrich import format_src_geo_label
    from app.ingestion.adapters.wazuh.mapper import extract_request_url

    alert_details = []
    event_row = await session.execute(
        select(Event)
        .options(selectinload(Event.alert_links).selectinload(EventAlert.alert))
        .where(Event.id == event_id)
    )
    event = event_row.scalar_one_or_none()
    if event:
        for link in event.alert_links:
            alert = link.alert
            triage_row = await session.execute(
                select(TriageResult).where(TriageResult.alert_id == alert.id)
            )
            triage = triage_row.scalar_one_or_none()
            alert_details.append(
                {
                    "alert_id": str(alert.id),
                    "severity": alert.severity,
                    "occurred_at": alert.occurred_at.isoformat(),
                    "rule_name": alert.rule_name,
                    "src_ip": str(alert.src_ip) if alert.src_ip else None,
                    "src_geo": format_src_geo_label(alert.normalized_fields),
                    "user_name": alert.user_name,
                    "host_name": alert.host_name,
                    "request_url": extract_request_url(
                        alert.raw_data,
                        normalized_fields=alert.normalized_fields,
                    ),
                    "triage_route": triage.route_decision.value if triage else None,
                    "triage_score": triage.rule_score if triage else None,
                }
            )

    return {
        **base,
        "entity_context_snapshot": event.entity_context_snapshot if event else None,
        "matched_playbooks": _matched_playbooks(event.primary_category if event else None),
        "investigations": investigations,
        "human_reviews": human_reviews,
        "dispositions": dispositions,
        "alert_details": alert_details,
    }


def _matched_playbooks(category: str | None) -> list[dict]:
    from app.playbooks.loader import match_playbooks

    return match_playbooks(category, limit=2)


async def get_alert_console_detail(session: AsyncSession, alert_id: UUID) -> dict | None:
    from app.triage.services.triage_service import TriageService

    triage_payload = await TriageService(session).get_alert_triage(alert_id)
    if triage_payload is None:
        return None

    link_result = await session.execute(
        select(EventAlert).where(EventAlert.alert_id == alert_id)
    )
    link = link_result.scalar_one_or_none()
    return {
        **triage_payload,
        "event_id": str(link.event_id) if link else None,
    }


async def list_pending_console_items(session: AsyncSession) -> dict:
    wl = await session.execute(
        select(WhitelistCandidate).where(WhitelistCandidate.status == WhitelistCandidateStatus.PENDING)
    )
    ps = await session.execute(
        select(ProfileUpdateSuggestion).where(
            ProfileUpdateSuggestion.status == ProfileUpdateStatus.PENDING
        )
    )
    disp = await session.execute(
        select(DispositionRecord)
        .where(DispositionRecord.status == DispositionStatus.SUGGESTED)
        .options(
            selectinload(DispositionRecord.investigation).selectinload(Investigation.event),
            selectinload(DispositionRecord.investigation).selectinload(Investigation.conclusion),
        )
        .order_by(DispositionRecord.created_at.desc())
    )
    hr = await session.execute(
        select(HumanReviewRequest).where(HumanReviewRequest.status == HumanReviewStatus.SENT)
    )
    sims = await session.execute(
        select(DispositionSimulation)
        .where(DispositionSimulation.approval_status == DispositionSimulationApprovalStatus.DRAFT)
        .options(
            selectinload(DispositionSimulation.investigation).selectinload(Investigation.event),
        )
        .order_by(DispositionSimulation.created_at.desc())
    )
    return {
        "whitelist_candidates": [
            {
                "id": str(c.id),
                "human_confirmations": c.human_confirmations,
                "reason": c.reason,
                "suggested_pattern": c.suggested_pattern,
            }
            for c in wl.scalars().all()
        ],
        "profile_suggestions": [
            {
                "id": str(s.id),
                "suggested_changes": s.suggested_changes,
            }
            for s in ps.scalars().all()
        ],
        "dispositions": [
            _pending_disposition_row(d)
            for d in disp.scalars().all()
        ],
        "disposition_simulations": [
            _pending_simulation_row(s) for s in sims.scalars().all()
        ],
        "human_review_requests": [
            {
                "id": str(r.id),
                "event_id": str(r.event_id),
                "question": r.question,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            }
            for r in hr.scalars().all()
        ],
    }


def _pending_disposition_row(record: DispositionRecord) -> dict:
    investigation = record.investigation
    event = investigation.event if investigation else None
    conclusion = investigation.conclusion if investigation else None
    return {
        "id": str(record.id),
        "suggested_action": record.suggested_action,
        "investigation_id": str(record.investigation_id),
        "event_id": str(investigation.event_id) if investigation else None,
        "event_title": event.title if event else None,
        "event_status": event.status.value if event else None,
        "aggregate_host_name": event.aggregate_host_name if event else None,
        "aggregate_user_name": event.aggregate_user_name if event else None,
        "primary_category": event.primary_category if event else None,
        "risk_score": event.risk_score if event else None,
        "verdict": conclusion.verdict.value if conclusion else None,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def _simulation_summary_row(record: DispositionSimulation) -> dict:
    impact = record.simulated_impact or {}
    return {
        "id": str(record.id),
        "action_type": record.action_type,
        "action_params": record.action_params,
        "approval_status": record.approval_status.value,
        "affected_host_count": impact.get("affected_host_count"),
        "estimated_downtime_minutes": impact.get("estimated_downtime_minutes"),
        "summary": impact.get("risk_notes", [""])[0] if impact.get("risk_notes") else None,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def _pending_simulation_row(record: DispositionSimulation) -> dict:
    investigation = record.investigation
    event = investigation.event if investigation else None
    impact = record.simulated_impact or {}
    return {
        "id": str(record.id),
        "investigation_id": str(record.investigation_id),
        "action_type": record.action_type,
        "action_params": record.action_params,
        "simulated_impact": impact,
        "approval_status": record.approval_status.value,
        "event_id": str(investigation.event_id) if investigation else None,
        "event_title": event.title if event else None,
        "aggregate_host_name": event.aggregate_host_name if event else None,
        "aggregate_user_name": event.aggregate_user_name if event else None,
        "affected_host_count": impact.get("affected_host_count"),
        "estimated_downtime_minutes": impact.get("estimated_downtime_minutes"),
        "business_systems": impact.get("business_systems"),
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
