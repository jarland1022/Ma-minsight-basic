"""Triage layer models: scoring, routing, and formal whitelist rules."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin
from app.db.enums import (
    RouteDecision,
    WhitelistCandidateStatus,
    WhitelistRuleStatus,
    WhitelistRuleType,
)

if TYPE_CHECKING:
    from app.models.entity import EntityProfile
    from app.models.ingestion import Alert
    from app.models.investigation import Investigation
    from app.models.system import User


class TriageResult(Base, CreatedAtMixin):
    """Immutable triage outcome for a single alert (volume layer, not final verdict)."""

    __tablename__ = "triage_results"
    __table_args__ = (UniqueConstraint("alert_id", name="uq_triage_results_alert_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
    )
    dedup_hit: Mapped[bool] = mapped_column(default=False, nullable=False)
    profile_hint_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    whitelist_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("whitelist_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    rule_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    llm_assist_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_cache_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    route_decision: Mapped[RouteDecision] = mapped_column(nullable=False)
    route_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    triaged_at: Mapped[datetime] = mapped_column(nullable=False)

    alert: Mapped[Alert] = relationship(back_populates="triage_result")
    whitelist_rule: Mapped[WhitelistRule | None] = relationship(back_populates="triage_hits")


class WhitelistRule(Base, TimestampMixin):
    """Formal whitelist rule — only these may auto-archive alerts."""

    __tablename__ = "whitelist_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    rule_type: Mapped[WhitelistRuleType] = mapped_column(nullable=False)
    match_pattern: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    entity_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    confirmation_count: Mapped[int] = mapped_column(nullable=False, default=0)
    effective_from: Mapped[datetime] = mapped_column(nullable=False)
    effective_until: Mapped[datetime] = mapped_column(nullable=False)
    status: Mapped[WhitelistRuleStatus] = mapped_column(
        default=WhitelistRuleStatus.CANDIDATE,
        nullable=False,
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    audit_trail: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)

    entity_profile: Mapped[EntityProfile | None] = relationship(back_populates="whitelist_rules")
    triage_hits: Mapped[list[TriageResult]] = relationship(back_populates="whitelist_rule")
    promoted_from_candidates: Mapped[list[WhitelistCandidate]] = relationship(
        back_populates="promoted_rule",
    )


class WhitelistCandidate(Base, CreatedAtMixin):
    """Agent-suggested whitelist pattern pending human confirmations (>=3 to promote)."""

    __tablename__ = "whitelist_candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    suggested_pattern: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_confirmations: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[WhitelistCandidateStatus] = mapped_column(
        default=WhitelistCandidateStatus.PENDING,
        nullable=False,
    )
    promoted_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("whitelist_rules.id", ondelete="SET NULL"),
        nullable=True,
    )

    investigation: Mapped[Investigation] = relationship(back_populates="whitelist_candidates")
    promoted_rule: Mapped[WhitelistRule | None] = relationship(
        back_populates="promoted_from_candidates",
    )
