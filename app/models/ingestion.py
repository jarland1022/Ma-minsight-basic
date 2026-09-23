"""Alert ingestion and normalization models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin
from app.db.enums import AlertStatus

if TYPE_CHECKING:
    from app.models.investigation import EventAlert
    from app.models.triage import TriageResult


class DataSource(Base, TimestampMixin):
    """Registered upstream alert source (Wazuh, Elastic, etc.)."""

    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    adapter_type: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    cursor_state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    alerts: Mapped[list[Alert]] = relationship(back_populates="data_source")


class AlertDedupGroup(Base, CreatedAtMixin):
    """Dedup window grouping for repeated alerts."""

    __tablename__ = "alert_dedup_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    first_seen_at: Mapped[datetime] = mapped_column(nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    representative_alert_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="SET NULL"),
        nullable=True,
    )
    window_start: Mapped[datetime] = mapped_column(nullable=False)
    window_end: Mapped[datetime] = mapped_column(nullable=False)

    alerts: Mapped[list[Alert]] = relationship(
        back_populates="dedup_group",
        foreign_keys="Alert.dedup_group_id",
    )


class Alert(Base, CreatedAtMixin):
    """Standardized alert with full raw payload preserved."""

    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("data_source_id", "source_alert_id", name="uq_alerts_source_alert"),
        Index("ix_alerts_occurred_at", "occurred_at"),
        Index("ix_alerts_fingerprint", "fingerprint"),
        Index("ix_alerts_status", "status"),
        Index("ix_alerts_src_ip", "src_ip"),
        Index("ix_alerts_host_name", "host_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_alert_id: Mapped[str] = mapped_column(String(256), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    rule_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    severity: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    severity_raw: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(nullable=False)
    src_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    dst_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    src_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dst_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    host_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    process_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    process_cmdline: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    alert_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normalized_fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    dedup_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alert_dedup_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[AlertStatus] = mapped_column(default=AlertStatus.NEW, nullable=False)

    data_source: Mapped[DataSource] = relationship(back_populates="alerts")
    dedup_group: Mapped[AlertDedupGroup | None] = relationship(
        back_populates="alerts",
        foreign_keys=[dedup_group_id],
    )
    triage_result: Mapped[TriageResult | None] = relationship(
        back_populates="alert",
        uselist=False,
    )
    event_links: Mapped[list["EventAlert"]] = relationship(back_populates="alert")
