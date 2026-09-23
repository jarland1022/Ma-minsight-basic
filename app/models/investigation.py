"""Event aggregation and Agent investigation models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin
from app.db.enums import (
    EventStatus,
    InvestigationStatus,
    InvestigationVerdict,
    MessageRole,
    RiskLevel,
)

if TYPE_CHECKING:
    from app.models.defense_assets import (
        DispositionRecord,
        DispositionSimulation,
        JudgmentCase,
        ProfileUpdateSuggestion,
        RuleCandidate,
    )
    from app.models.entity import EntityProfileMemory
    from app.models.human_review import HumanReviewRequest
    from app.models.ingestion import Alert
    from app.models.system import User
    from app.models.triage import WhitelistCandidate


class Event(Base, CreatedAtMixin):
    """Investigation unit: aggregated alerts (host + user + category + 24h window)."""

    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_event_key", "event_key"),
        Index("ix_events_status", "status"),
        Index(
            "ix_events_aggregate_dims",
            "aggregate_host_name",
            "aggregate_user_name",
            "aggregate_category",
            "aggregate_window_start",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    primary_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    alert_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_alert_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_alert_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[EventStatus] = mapped_column(default=EventStatus.PENDING_REVIEW, nullable=False)
    queue_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Aggregation key dimensions (option B): host + user + category + 24h window
    aggregate_host_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    aggregate_user_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    aggregate_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    aggregate_window_start: Mapped[datetime | None] = mapped_column(nullable=True)
    entity_context_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    correlation_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    related_event_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )

    alert_links: Mapped[list[EventAlert]] = relationship(back_populates="event")
    investigations: Mapped[list[Investigation]] = relationship(back_populates="event")
    human_review_requests: Mapped[list[HumanReviewRequest]] = relationship(back_populates="event")


class EventAlert(Base, CreatedAtMixin):
    """Many-to-many link between events and alerts."""

    __tablename__ = "event_alerts"
    __table_args__ = (
        UniqueConstraint("event_id", "alert_id", name="uq_event_alerts_pair"),
        UniqueConstraint("alert_id", name="uq_event_alerts_alert_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
    )
    added_at: Mapped[datetime] = mapped_column(nullable=False)

    event: Mapped[Event] = relationship(back_populates="alert_links")
    alert: Mapped[Alert] = relationship(back_populates="event_links")


class InvestigationSop(Base, TimestampMixin):
    """Category-specific investigation guidance (principles, not fixed steps)."""

    __tablename__ = "investigation_sops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_category: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    guidance_text: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_skills: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    hypothesis_template: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    termination_policy: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    investigations: Mapped[list[Investigation]] = relationship(back_populates="sop")


class Investigation(Base, CreatedAtMixin):
    """Agent deep-review session for an event."""

    __tablename__ = "investigations"
    __table_args__ = (Index("ix_investigations_event_id", "event_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    sop_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigation_sops.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[InvestigationStatus] = mapped_column(
        default=InvestigationStatus.RUNNING,
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    max_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_input: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_output: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skill_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    closure_requested_at: Mapped[datetime | None] = mapped_column(nullable=True)
    closure_retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    event: Mapped[Event] = relationship(back_populates="investigations")
    sop: Mapped[InvestigationSop | None] = relationship(back_populates="investigations")
    tool_calls: Mapped[list[InvestigationToolCall]] = relationship(back_populates="investigation")
    messages: Mapped[list[InvestigationMessage]] = relationship(back_populates="investigation")
    conclusion: Mapped[InvestigationConclusion | None] = relationship(
        back_populates="investigation",
        uselist=False,
    )
    human_review_requests: Mapped[list[HumanReviewRequest]] = relationship(
        back_populates="investigation",
    )
    whitelist_candidates: Mapped[list[WhitelistCandidate]] = relationship(
        back_populates="investigation",
    )
    judgment_cases: Mapped[list[JudgmentCase]] = relationship(back_populates="investigation")
    rule_candidates: Mapped[list[RuleCandidate]] = relationship(back_populates="investigation")
    profile_update_suggestions: Mapped[list[ProfileUpdateSuggestion]] = relationship(
        back_populates="investigation",
    )
    disposition_records: Mapped[list[DispositionRecord]] = relationship(
        back_populates="investigation",
    )
    disposition_simulations: Mapped[list[DispositionSimulation]] = relationship(
        back_populates="investigation",
    )
    profile_memories_created: Mapped[list[EntityProfileMemory]] = relationship(
        back_populates="source_investigation",
    )
    audits: Mapped[list[InvestigationAudit]] = relationship(back_populates="investigation")


class InvestigationAudit(Base, CreatedAtMixin):
    """Supervisor audit of investigation quality (rules or LLM)."""

    __tablename__ = "investigation_audits"
    __table_args__ = (Index("ix_investigation_audits_inv", "investigation_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    audit_type: Mapped[str] = mapped_column(String(32), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    findings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    supervisor_model: Mapped[str] = mapped_column(String(64), nullable=False, default="rules")

    investigation: Mapped[Investigation] = relationship(back_populates="audits")


class InvestigationToolCall(Base, CreatedAtMixin):
    """Full Skill invocation trace for replay and case library."""

    __tablename__ = "investigation_tool_calls"
    __table_args__ = (
        Index("ix_investigation_tool_calls_investigation", "investigation_id", "step_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    skill_name: Mapped[str] = mapped_column(String(128), nullable=False)
    skill_input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    skill_output: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    called_at: Mapped[datetime] = mapped_column(nullable=False)

    investigation: Mapped[Investigation] = relationship(back_populates="tool_calls")


class InvestigationConclusion(Base, CreatedAtMixin):
    """Structured Agent review outcome with evidence references."""

    __tablename__ = "investigation_conclusions"
    __table_args__ = (UniqueConstraint("investigation_id", name="uq_investigation_conclusions_inv"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    verdict: Mapped[InvestigationVerdict] = mapped_column(nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_refs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    human_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_info: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    suggested_assets: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    hypotheses_evaluated: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    refutation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_closure_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    refutation_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    closure_checks: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    closure_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_overridden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    overridden_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    overridden_at: Mapped[datetime | None] = mapped_column(nullable=True)

    investigation: Mapped[Investigation] = relationship(back_populates="conclusion")
    overridden_by: Mapped[User | None] = relationship(foreign_keys=[overridden_by_id])


class InvestigationMessage(Base, CreatedAtMixin):
    """Full ReAct message history for replay and regression."""

    __tablename__ = "investigation_messages"
    __table_args__ = (
        Index("ix_investigation_messages_inv_seq", "investigation_id", "sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[MessageRole] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_call_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    investigation: Mapped[Investigation] = relationship(back_populates="messages")
