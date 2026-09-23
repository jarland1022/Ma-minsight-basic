"""Human-in-the-loop review via IM channels."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin
from app.db.enums import AuditSampleReason, HumanReviewStatus, ImChannel, InvestigationVerdict

if TYPE_CHECKING:
    from app.models.ingestion import Alert
    from app.models.investigation import Event, Investigation
    from app.models.system import User


class HumanReviewRequest(Base, CreatedAtMixin):
    """IM协查 request when Agent verdict is insufficient_information."""

    __tablename__ = "human_review_requests"
    __table_args__ = (Index("ix_human_review_requests_event_id", "event_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[ImChannel] = mapped_column(nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[HumanReviewStatus] = mapped_column(
        default=HumanReviewStatus.SENT,
        nullable=False,
    )
    external_msg_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(nullable=True)

    investigation: Mapped[Investigation] = relationship(back_populates="human_review_requests")
    event: Mapped[Event] = relationship(back_populates="human_review_requests")
    responses: Mapped[list[HumanReviewResponse]] = relationship(back_populates="request")


class HumanReviewResponse(Base, CreatedAtMixin):
    """Parsed operator reply routed by event_id."""

    __tablename__ = "human_review_responses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("human_review_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    responder: Mapped[str | None] = mapped_column(String(256), nullable=True)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_reinvestigation: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    request: Mapped[HumanReviewRequest] = relationship(back_populates="responses")


class AuditSample(Base, CreatedAtMixin):
    """Ring-outside sampling audit for low-risk archived alerts/events."""

    __tablename__ = "audit_samples"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
    )
    sample_reason: Mapped[AuditSampleReason] = mapped_column(nullable=False)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    review_verdict: Mapped[InvestigationVerdict | None] = mapped_column(nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    alert: Mapped[Alert | None] = relationship()
    event: Mapped[Event | None] = relationship()
    reviewer: Mapped[User | None] = relationship()
