"""Investigation context passed to Skills and Agent loop."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AlertBrief(BaseModel):
    id: UUID
    occurred_at: datetime
    rule_id: str | None = None
    rule_name: str | None = None
    severity: int = 3
    src_ip: str | None = None
    src_geo: str | None = None
    user_name: str | None = None
    host_name: str | None = None
    request_url: str | None = None
    alert_category: str | None = None
    triage_rule_score: float | None = None
    triage_route: str | None = None


class EventBrief(BaseModel):
    id: UUID
    title: str | None = None
    primary_category: str | None = None
    queue_priority: int = 0
    risk_score: float = 0.0
    alert_count: int = 0
    first_alert_at: datetime | None = None
    last_alert_at: datetime | None = None
    aggregate_host_name: str | None = None
    aggregate_user_name: str | None = None


class SopBrief(BaseModel):
    id: UUID
    name: str
    guidance_text: str
    recommended_skills: list[Any] = Field(default_factory=list)
    hypothesis_template: dict[str, Any] | None = None
    termination_policy: dict[str, Any] | None = None


class PlaybookBrief(BaseModel):
    id: str
    name: str
    summary: str = ""
    domain: str | None = None
    mitre_attack: list[str] = Field(default_factory=list)
    investigation_steps: list[str] = Field(default_factory=list)
    runtime_skills: list[str] = Field(default_factory=list)
    human_questions: list[str] = Field(default_factory=list)


class InvestigationContext(BaseModel):
    investigation_id: UUID
    event: EventBrief
    alerts: list[AlertBrief] = Field(default_factory=list)
    sop: SopBrief | None = None
    playbooks: list[PlaybookBrief] = Field(default_factory=list)
    reference_cases: list[dict[str, Any]] = Field(default_factory=list)
    human_review_context: dict[str, Any] | None = None
    model_name: str = "deepseek-chat"
    conclusion_payload: dict[str, Any] | None = None
    disposition_simulation_enabled: bool = False
    hypothesis_template_enabled: bool = True

    model_config = {"arbitrary_types_allowed": True}
