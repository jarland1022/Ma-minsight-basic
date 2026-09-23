"""Triage pipeline schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.enums import RouteDecision


class AlertSnapshot(BaseModel):
    id: UUID
    data_source_id: UUID
    data_source_name: str
    source_alert_id: str
    fingerprint: str
    rule_id: str | None = None
    rule_name: str | None = None
    severity: int = 3
    occurred_at: datetime
    src_ip: str | None = None
    dst_ip: str | None = None
    user_name: str | None = None
    host_name: str | None = None
    file_hash: str | None = None
    alert_category: str | None = None
    normalized_fields: dict[str, Any] = Field(default_factory=dict)
    raw_data: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class TriageContext(BaseModel):
    alert: AlertSnapshot

    dedup_hit: bool = False
    dedup_group_id: UUID | None = None
    is_representative: bool = True

    whitelist_rule_id: UUID | None = None
    whitelist_matched: bool = False

    profile_hint_score: float = 0.0
    profile_hint_details: list[str] = Field(default_factory=list)

    rule_score: float = 0.0
    rule_score_breakdown: dict[str, float] = Field(default_factory=dict)
    effective_score: float = 0.0

    llm_assist_score: float | None = None
    llm_cache_key: str | None = None

    route_decision: RouteDecision | None = None
    route_reason: dict[str, Any] = Field(default_factory=dict)
    short_circuit: bool = False
    skipped_steps: list[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}
