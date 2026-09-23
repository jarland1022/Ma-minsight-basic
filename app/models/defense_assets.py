"""Defense asset沉淀: cases, rules, profile updates, disposition."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin
from app.db.enums import (
    CandidateStatus,
    DispositionSimulationApprovalStatus,
    DispositionStatus,
    InvestigationVerdict,
    ProfileUpdateStatus,
)

if TYPE_CHECKING:
    from app.models.entity import EntityProfile
    from app.models.investigation import Investigation
    from app.models.system import User


class JudgmentCase(Base, CreatedAtMixin):
    """Reference case with full investigation trace — for prompt injection, not conclusion reuse."""

    __tablename__ = "judgment_cases"
    __table_args__ = (
        Index("ix_judgment_cases_category", "alert_category"),
        Index("ix_judgment_cases_entity_tags", "entity_tags", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    feature_summary: Mapped[str] = mapped_column(Text, nullable=False)
    alert_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_tags: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    investigation_trace: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    verdict: Mapped[InvestigationVerdict] = mapped_column(nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    human_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Reserved for pgvector migration in phase 7; store as float array until then
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)

    investigation: Mapped[Investigation] = relationship(back_populates="judgment_cases")


class RuleCandidate(Base, CreatedAtMixin):
    """Detection rule draft suggested by Agent investigation."""

    __tablename__ = "rule_candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_draft: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CandidateStatus] = mapped_column(default=CandidateStatus.PENDING, nullable=False)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    investigation: Mapped[Investigation] = relationship(back_populates="rule_candidates")
    reviewed_by: Mapped[User | None] = relationship()


class ProfileUpdateSuggestion(Base, CreatedAtMixin):
    """Suggested entity profile changes pending operator approval."""

    __tablename__ = "profile_update_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    suggested_changes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[ProfileUpdateStatus] = mapped_column(
        default=ProfileUpdateStatus.PENDING,
        nullable=False,
    )
    applied_at: Mapped[datetime | None] = mapped_column(nullable=True)

    investigation: Mapped[Investigation] = relationship(back_populates="profile_update_suggestions")
    entity_profile: Mapped[EntityProfile] = relationship(
        back_populates="profile_update_suggestions",
    )


class DispositionRecord(Base, CreatedAtMixin):
    """Suggested vs confirmed disposition — no auto-enforcement."""

    __tablename__ = "disposition_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    suggested_action: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[DispositionStatus] = mapped_column(
        default=DispositionStatus.SUGGESTED,
        nullable=False,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    investigation: Mapped[Investigation] = relationship(back_populates="disposition_records")
    confirmed_by: Mapped[User | None] = relationship()


class DispositionSimulation(Base, CreatedAtMixin):
    """Read-only disposition impact simulation — never auto-executes."""

    __tablename__ = "disposition_simulations"
    __table_args__ = (Index("ix_disposition_simulations_inv", "investigation_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    action_params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    simulated_impact: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    approval_status: Mapped[DispositionSimulationApprovalStatus] = mapped_column(
        SAEnum(
            DispositionSimulationApprovalStatus,
            native_enum=False,
            length=32,
        ),
        default=DispositionSimulationApprovalStatus.DRAFT,
        nullable=False,
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    investigation: Mapped[Investigation] = relationship(back_populates="disposition_simulations")
    approved_by: Mapped[User | None] = relationship()
