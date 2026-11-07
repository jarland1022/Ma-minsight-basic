"""Cancel human-review requests superseded by newer investigations or ops failures."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.failure import is_ops_failure_class
from app.core.datetime_utils import utc_now
from app.db.enums import EventStatus, HumanReviewStatus, InvestigationStatus
from app.models.human_review import HumanReviewRequest
from app.models.investigation import Event, Investigation

_SYSTEM_ERROR_PATTERN = re.compile(r"LLM error|404 Not Found|自动调查未完成", re.I)


def is_system_error_human_query(question: str | None) -> bool:
    """Heuristic for UI / admin review candidates — NOT sufficient alone to auto-cancel."""
    if not question:
        return False
    return bool(_SYSTEM_ERROR_PATTERN.search(question))


def _mark_cancelled(
    req: HumanReviewRequest,
    *,
    reason: str,
    actor: str,
) -> None:
    req.status = HumanReviewStatus.CANCELLED
    req.cancel_reason = reason
    req.cancelled_at = utc_now()
    req.cancelled_by = actor


async def _latest_investigation(session: AsyncSession, event_id: UUID) -> Investigation | None:
    result = await session.execute(
        select(Investigation)
        .options(selectinload(Investigation.conclusion))
        .where(Investigation.event_id == event_id)
        .order_by(Investigation.started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def cancel_obsolete_sent_reviews_for_event(
    session: AsyncSession,
    event_id: UUID,
    *,
    current_investigation_id: UUID,
    event_status: EventStatus,
) -> int:
    """Cancel open协查单 tied to older investigations or non-pending events."""
    result = await session.execute(
        select(HumanReviewRequest).where(
            HumanReviewRequest.event_id == event_id,
            HumanReviewRequest.status == HumanReviewStatus.SENT,
        )
    )
    cancelled = 0
    for req in result.scalars().all():
        if event_status != EventStatus.HUMAN_PENDING:
            _mark_cancelled(
                req,
                reason="event_no_longer_human_pending",
                actor="system",
            )
            cancelled += 1
            continue
        if req.investigation_id != current_investigation_id:
            _mark_cancelled(
                req,
                reason="superseded_by_newer_investigation",
                actor="system",
            )
            cancelled += 1
    return cancelled


async def cancel_sent_reviews_for_ops_investigation(
    session: AsyncSession,
    *,
    investigation_id: UUID,
    event_id: UUID,
    reason: str = "ops_failure_reclassification",
    actor: str = "system",
) -> int:
    """Cancel SENT HR linked to a confirmed ops-failed investigation (structured, not regex)."""
    result = await session.execute(
        select(HumanReviewRequest).where(
            HumanReviewRequest.event_id == event_id,
            HumanReviewRequest.status == HumanReviewStatus.SENT,
            HumanReviewRequest.investigation_id == investigation_id,
        )
    )
    cancelled = 0
    for req in result.scalars().all():
        _mark_cancelled(req, reason=reason, actor=actor)
        cancelled += 1
    return cancelled


async def cancel_all_obsolete_sent_reviews(session: AsyncSession) -> int:
    """Sweep SENT requests that no longer match latest investigation / event / ops failure."""
    result = await session.execute(
        select(HumanReviewRequest)
        .options(
            selectinload(HumanReviewRequest.event),
            selectinload(HumanReviewRequest.investigation).selectinload(Investigation.conclusion),
        )
        .where(HumanReviewRequest.status == HumanReviewStatus.SENT)
    )
    cancelled = 0
    for req in result.scalars().all():
        event = req.event or await session.get(Event, req.event_id)
        if event is None or event.status != EventStatus.HUMAN_PENDING:
            _mark_cancelled(req, reason="event_no_longer_human_pending", actor="system")
            cancelled += 1
            continue

        inv = req.investigation or await session.get(Investigation, req.investigation_id)
        if inv is not None:
            if inv.status == InvestigationStatus.FAILED or (
                inv.status == InvestigationStatus.DEGRADED and is_ops_failure_class(inv.failure_class)
            ):
                _mark_cancelled(req, reason="ops_failure_reclassification", actor="system")
                if inv.conclusion is not None and not inv.conclusion.invalidated_as_ops_failure:
                    inv.conclusion.invalidated_as_ops_failure = True
                    inv.conclusion.invalidated_at = utc_now()
                    inv.conclusion.invalidated_reason = "ops_failure_reclassification"
                cancelled += 1
                continue
            if inv.conclusion is not None and inv.conclusion.invalidated_as_ops_failure:
                _mark_cancelled(req, reason="conclusion_invalidated_as_ops_failure", actor="system")
                cancelled += 1
                continue

        latest = await _latest_investigation(session, req.event_id)
        if latest is None or latest.id != req.investigation_id:
            _mark_cancelled(req, reason="superseded_by_newer_investigation", actor="system")
            cancelled += 1
    return cancelled


async def list_ambiguous_system_error_reviews(session: AsyncSession, *, limit: int = 100) -> list[HumanReviewRequest]:
    """Candidates for admin review: heuristic match but NOT linked to structured ops failure.

    Must not be auto-cancelled (D-FAIL-09).
    """
    result = await session.execute(
        select(HumanReviewRequest)
        .options(selectinload(HumanReviewRequest.investigation))
        .where(HumanReviewRequest.status == HumanReviewStatus.SENT)
        .order_by(HumanReviewRequest.sent_at.desc())
        .limit(limit)
    )
    out: list[HumanReviewRequest] = []
    for req in result.scalars().all():
        if not is_system_error_human_query(req.question):
            continue
        inv = req.investigation
        if inv is not None and (
            inv.status == InvestigationStatus.FAILED
            or is_ops_failure_class(inv.failure_class)
            or (inv.conclusion is not None and inv.conclusion.invalidated_as_ops_failure)
        ):
            # Structured path — not ambiguous
            continue
        out.append(req)
    return out
