"""Entity profile, threat intel, and on-duty knowledge models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin
from app.db.enums import (
    AssetCriticality,
    EntityMemoryType,
    EntityType,
    IocType,
    ThreatIntelVerdict,
)

if TYPE_CHECKING:
    from app.models.defense_assets import ProfileUpdateSuggestion
    from app.models.investigation import Investigation
    from app.models.triage import WhitelistRule


class EntityProfile(Base, TimestampMixin):
    """Structured asset/account/host context queried in real time by Agent skills."""

    __tablename__ = "entity_profiles"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_key", name="uq_entity_profiles_type_key"),
        Index("ix_entity_profiles_entity_key", "entity_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[EntityType] = mapped_column(nullable=False)
    entity_key: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    owner_team: Mapped[str | None] = mapped_column(String(128), nullable=True)
    asset_criticality: Mapped[AssetCriticality] = mapped_column(
        default=AssetCriticality.MEDIUM,
        nullable=False,
    )
    is_known_scanner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_jump_host: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_decommissioned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    memories: Mapped[list[EntityProfileMemory]] = relationship(back_populates="entity_profile")
    stats: Mapped[list[EntityProfileStat]] = relationship(back_populates="entity_profile")
    whitelist_rules: Mapped[list[WhitelistRule]] = relationship(back_populates="entity_profile")
    profile_update_suggestions: Mapped[list["ProfileUpdateSuggestion"]] = relationship(
        back_populates="entity_profile",
    )


class EntityProfileMemory(Base, CreatedAtMixin):
    """Fuzzy memory for Agent hints — MUST NOT be used for auto-archive."""

    __tablename__ = "entity_profile_memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    memory_type: Mapped[EntityMemoryType] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    source_investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="SET NULL"),
        nullable=True,
    )
    valid_until: Mapped[datetime | None] = mapped_column(nullable=True)

    entity_profile: Mapped[EntityProfile] = relationship(back_populates="memories")
    source_investigation: Mapped[Investigation | None] = relationship(
        back_populates="profile_memories_created",
    )


class EntityProfileStat(Base, CreatedAtMixin):
    """Rolling alert/behavior stats aligned with Agent query fingerprints."""

    __tablename__ = "entity_profile_stats"
    __table_args__ = (
        UniqueConstraint("entity_profile_id", "window_days", name="uq_entity_profile_stats_window"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    alert_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alert_by_category: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    external_conn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_computed_at: Mapped[datetime] = mapped_column(nullable=False)
    query_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)

    entity_profile: Mapped[EntityProfile] = relationship(back_populates="stats")


class EntityRelation(Base, CreatedAtMixin):
    """Directed relationship between entities for graph traversal during investigation."""

    __tablename__ = "entity_relations"
    __table_args__ = (
        Index("ix_entity_relations_from", "from_entity_type", "from_entity_key"),
        Index("ix_entity_relations_to", "to_entity_type", "to_entity_key"),
        Index("ix_entity_relations_type", "relation_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_entity_type: Mapped[EntityType] = mapped_column(nullable=False)
    from_entity_key: Mapped[str] = mapped_column(String(256), nullable=False)
    to_entity_type: Mapped[EntityType] = mapped_column(nullable=False)
    to_entity_key: Mapped[str] = mapped_column(String(256), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="seed")
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    valid_from: Mapped[datetime | None] = mapped_column(nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(nullable=True)


class OnDutyKnowledge(Base, TimestampMixin):
    """Operator/on-call contextual knowledge (e.g. internal scanner IPs)."""

    __tablename__ = "on_duty_knowledge"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(nullable=False)
    effective_until: Mapped[datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ThreatIntelEntry(Base, CreatedAtMixin):
    """Cached threat intel lookup — intermediate evidence, not final verdict."""

    __tablename__ = "threat_intel_entries"
    __table_args__ = (
        Index("ix_threat_intel_ioc", "ioc_type", "ioc_value"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ioc_type: Mapped[IocType] = mapped_column(nullable=False)
    ioc_value: Mapped[str] = mapped_column(String(512), nullable=False)
    verdict: Mapped[ThreatIntelVerdict] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    raw_response: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
