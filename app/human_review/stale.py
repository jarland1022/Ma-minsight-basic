"""Cancel human-review requests superseded by newer investigations."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import EventStatus, HumanReviewStatus
from app.models.human_review import HumanReviewRequest
from app.models.investigation import Event, Investigation

_SYSTEM_ERROR_PATTERN = re.compile(r"LLM error|404 Not Found|自动调查未完成", re.I)


def is_system_error_human_query(question: str | None) -> bool:
    if not question:
        return False
    return bool(_SYSTEM_ERROR_PATTERN.search(question))


async def _latest_investigation(session: AsyncSession, event_id: UUID) -> Investigation | None:
    result = await session.execute(
        select(Investigation)
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
            req.status = HumanReviewStatus.CANCELLED
            cancelled += 1
            continue
        if req.investigation_id != current_investigation_id:
            req.status = HumanReviewStatus.CANCELLED
            cancelled += 1
    return cancelled


async def cancel_all_obsolete_sent_reviews(session: AsyncSession) -> int:
    """Sweep all SENT requests that no longer match the latest investigation or event state."""
    result = await session.execute(
        select(HumanReviewRequest)
        .options(selectinload(HumanReviewRequest.event))
        .where(HumanReviewRequest.status == HumanReviewStatus.SENT)
    )
    cancelled = 0
    for req in result.scalars().all():
        event = req.event or await session.get(Event, req.event_id)
        if event is None or event.status != EventStatus.HUMAN_PENDING:
            req.status = HumanReviewStatus.CANCELLED
            cancelled += 1
            continue
        latest = await _latest_investigation(session, req.event_id)
        if latest is None or latest.id != req.investigation_id:
            req.status = HumanReviewStatus.CANCELLED
            cancelled += 1
    return cancelled
