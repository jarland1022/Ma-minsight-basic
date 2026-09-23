"""Build InvestigationContext from database."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.context import AlertBrief, EventBrief, InvestigationContext, PlaybookBrief, SopBrief
from app.geoip.enrich import format_src_geo_label
from app.ingestion.adapters.wazuh.mapper import extract_request_url
from app.db.enums import HumanReviewStatus
from app.playbooks.loader import match_playbooks
from app.services.system_config import get_config_bool
from app.defense_assets.config import load_defense_asset_config
from app.defense_assets.disposition.config import load_disposition_config
from app.defense_assets.retrieval import fetch_reference_cases
from app.models.human_review import HumanReviewRequest, HumanReviewResponse
from app.models.investigation import Event, EventAlert, InvestigationSop
from app.models.triage import TriageResult


async def build_investigation_context(
    session: AsyncSession,
    *,
    investigation_id: UUID,
    event_id: UUID,
    model_name: str,
    alert_limit: int = 20,
) -> InvestigationContext:
    result = await session.execute(
        select(Event)
        .options(selectinload(Event.alert_links).selectinload(EventAlert.alert))
        .where(Event.id == event_id)
    )
    event = result.scalar_one()

    alert_briefs: list[AlertBrief] = []
    links = sorted(event.alert_links, key=lambda link: link.alert.occurred_at)
    for link in links[:alert_limit]:
        alert = link.alert
        triage_row = await session.execute(
            select(TriageResult).where(TriageResult.alert_id == alert.id)
        )
        triage = triage_row.scalar_one_or_none()
        alert_briefs.append(
            AlertBrief(
                id=alert.id,
                occurred_at=alert.occurred_at,
                rule_id=alert.rule_id,
                rule_name=alert.rule_name,
                severity=alert.severity,
                src_ip=str(alert.src_ip) if alert.src_ip else None,
                src_geo=format_src_geo_label(alert.normalized_fields),
                user_name=alert.user_name,
                host_name=alert.host_name,
                request_url=extract_request_url(
                    alert.raw_data,
                    normalized_fields=alert.normalized_fields,
                ),
                alert_category=alert.alert_category,
                triage_rule_score=triage.rule_score if triage else None,
                triage_route=triage.route_decision.value if triage else None,
            )
        )

    sop = None
    if event.primary_category:
        sop_result = await session.execute(
            select(InvestigationSop)
            .where(
                InvestigationSop.alert_category == event.primary_category,
                InvestigationSop.is_active.is_(True),
            )
            .order_by(InvestigationSop.version.desc())
            .limit(1)
        )
        sop_row = sop_result.scalar_one_or_none()
        if sop_row:
            sop = SopBrief(
                id=sop_row.id,
                name=sop_row.name,
                guidance_text=sop_row.guidance_text,
                recommended_skills=sop_row.recommended_skills or [],
                hypothesis_template=sop_row.hypothesis_template,
                termination_policy=sop_row.termination_policy,
            )

    defense_config = await load_defense_asset_config(session)
    reference_cases = await fetch_reference_cases(session, event=event, config=defense_config)

    human_review_context = await _load_human_review_context(session, event_id)
    disposition_config = await load_disposition_config(session)
    hypothesis_enabled = await get_config_bool(
        session, "investigation.hypothesis_template_enabled", True
    )
    playbooks = [
        PlaybookBrief(
            id=str(p["id"]),
            name=str(p["name"]),
            summary=str(p.get("summary") or ""),
            domain=p.get("domain"),
            mitre_attack=list(p.get("mitre_attack") or []),
            investigation_steps=list(p.get("investigation_steps") or []),
            runtime_skills=list(p.get("runtime_skills") or []),
            human_questions=list(p.get("human_questions") or []),
        )
        for p in match_playbooks(event.primary_category, limit=2)
    ]

    return InvestigationContext(
        investigation_id=investigation_id,
        event=EventBrief(
            id=event.id,
            title=event.title,
            primary_category=event.primary_category,
            queue_priority=event.queue_priority,
            risk_score=event.risk_score,
            alert_count=event.alert_count,
            first_alert_at=event.first_alert_at,
            last_alert_at=event.last_alert_at,
            aggregate_host_name=event.aggregate_host_name,
            aggregate_user_name=event.aggregate_user_name,
        ),
        alerts=alert_briefs,
        sop=sop,
        playbooks=playbooks,
        reference_cases=reference_cases,
        human_review_context=human_review_context,
        model_name=model_name,
        disposition_simulation_enabled=disposition_config.simulation_enabled,
        hypothesis_template_enabled=hypothesis_enabled,
    )


async def _load_human_review_context(session: AsyncSession, event_id: UUID) -> dict | None:
    req_result = await session.execute(
        select(HumanReviewRequest)
        .where(
            HumanReviewRequest.event_id == event_id,
            HumanReviewRequest.status == HumanReviewStatus.ANSWERED,
        )
        .order_by(HumanReviewRequest.answered_at.desc())
        .limit(1)
    )
    request = req_result.scalar_one_or_none()
    if request is None:
        return None

    resp_result = await session.execute(
        select(HumanReviewResponse)
        .where(HumanReviewResponse.request_id == request.id)
        .order_by(HumanReviewResponse.created_at.desc())
        .limit(1)
    )
    response = resp_result.scalar_one_or_none()
    if response is None:
        return None

    return {
        "human_query": request.question,
        "raw_content": response.raw_content,
        "parsed_content": response.parsed_content,
        "responder": response.responder,
        "answered_at": request.answered_at.isoformat() if request.answered_at else None,
    }
