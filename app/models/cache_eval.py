"""Cache metadata, regression tests, and health checks."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin
from app.db.enums import CacheType, HealthCheckStage, InvestigationVerdict


class CacheEntry(Base, CreatedAtMixin):
    """PostgreSQL-backed cache metadata; Redis holds hot values."""

    __tablename__ = "cache_entries"
    __table_args__ = (Index("ix_cache_entries_type_expires", "cache_type", "expires_at"),)

    cache_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    cache_type: Mapped[CacheType] = mapped_column(nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)


class RegressionTestCase(Base, CreatedAtMixin):
    """Labeled alert sample for prompt/model regression."""

    __tablename__ = "regression_test_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    alert_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expected_verdict: Mapped[InvestigationVerdict] = mapped_column(nullable=False)
    expected_skills: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    forbidden_skills: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class RegressionTestRun(Base, CreatedAtMixin):
    """Batch regression execution with aggregate metrics and per-case details."""

    __tablename__ = "regression_test_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trigger: Mapped[str] = mapped_column(String(128), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sop_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    run_at: Mapped[datetime] = mapped_column(nullable=False)


class HealthCheckScenario(Base, CreatedAtMixin):
    """Synthetic alert scenario for end-to-end pipeline validation."""

    __tablename__ = "health_check_scenarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    inject_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expected_stage: Mapped[HealthCheckStage] = mapped_column(nullable=False)
    expected_outcome: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    runs: Mapped[list[HealthCheckRun]] = relationship(back_populates="scenario")


class HealthCheckRun(Base, CreatedAtMixin):
    """Result of executing a health check scenario."""

    __tablename__ = "health_check_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("health_check_scenarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    passed: Mapped[bool] = mapped_column(nullable=False)
    stage_results: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_at: Mapped[datetime] = mapped_column(nullable=False)

    scenario: Mapped[HealthCheckScenario] = relationship(back_populates="runs")
