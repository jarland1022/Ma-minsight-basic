"""Build judgment_cases from investigations."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import HumanReviewStatus
from app.models.defense_assets import JudgmentCase
from app.models.human_review import HumanReviewRequest, HumanReviewResponse
from app.models.investigation import Event, Investigation, InvestigationConclusion, InvestigationToolCall


def build_entity_tags(event: Event, alerts: list[Any]) -> dict[str, Any]:
    tags: dict[str, Any] = {
        "category": event.primary_category,
        "host": event.aggregate_host_name,
        "user": event.aggregate_user_name,
    }
    if alerts:
        first = alerts[0]
        if getattr(first, "src_ip", None):
            tags["src_ip"] = str(first.src_ip)
        if getattr(first, "host_name", None):
            tags["host_name"] = first.host_name
        if getattr(first, "user_name", None):
            tags["user_name"] = first.user_name
    return {k: v for k, v in tags.items() if v}


def build_investigation_trace(tool_calls: list[InvestigationToolCall]) -> list[dict[str, Any]]:
    return [
        {
            "step": tc.step_number,
            "skill": tc.skill_name,
            "success": tc.success,
            "summary": tc.output_summary or "",
        }
        for tc in sorted(tool_calls, key=lambda x: x.step_number)
    ]


async def load_human_feedback(session: AsyncSession, event_id: UUID) -> str | None:
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
    return response.parsed_content or response.raw_content


async def build_judgment_case(
    session: AsyncSession,
    *,
    investigation: Investigation,
    event: Event,
    conclusion: InvestigationConclusion,
) -> JudgmentCase:
    await session.refresh(investigation, ["tool_calls"])
    suggested = conclusion.suggested_assets or {}
    jc_hint = suggested.get("judgment_case") if isinstance(suggested, dict) else {}
    if not isinstance(jc_hint, dict):
        jc_hint = {}

    feature_summary = jc_hint.get("feature_summary") or (conclusion.reasoning or "")[:200]
    entity_tags = jc_hint.get("entity_tags") if isinstance(jc_hint.get("entity_tags"), dict) else {}
    if not entity_tags:
        entity_tags = build_entity_tags(event, [])

    human_feedback = await load_human_feedback(session, event.id)
    trace = build_investigation_trace(list(investigation.tool_calls))

    return JudgmentCase(
        investigation_id=investigation.id,
        feature_summary=str(feature_summary),
        alert_category=event.primary_category,
        entity_tags=entity_tags,
        investigation_trace=trace,
        verdict=conclusion.verdict,
        reasoning=conclusion.reasoning,
        human_feedback=human_feedback,
    )
