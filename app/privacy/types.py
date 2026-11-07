"""Shared types for egress protection."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class FieldClass(StrEnum):
    SECRET_NEVER = "SECRET_NEVER"
    PII_DEFAULT = "PII_DEFAULT"
    ANALYTIC_ALLOWED = "ANALYTIC_ALLOWED"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    UNKNOWN = "UNKNOWN"


class EgressChannel(StrEnum):
    LLM = "llm"
    TI = "ti"
    WECOM = "wecom"
    EMBED = "embed"
    WEBHOOK = "webhook"
    SKILL_HTTP = "skill_http"


class DestinationClass(StrEnum):
    THIRD_PARTY = "third_party"
    CUSTOMER_CONTROLLED = "customer_controlled"
    UNKNOWN = "unknown"


class ContentType(StrEnum):
    CHAT_MESSAGES = "chat_messages"
    JSON = "json"
    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"
    QUERY_PARAMS = "query_params"


@dataclass
class EgressContext:
    investigation_id: str | None = None
    event_id: str | None = None
    correlation_id: str | None = None
    scope_id: str | None = None  # customer/env isolation for pseudonyms


@dataclass
class ProtectedPayload:
    payload: Any
    policy_id: str
    policy_version: int
    transforms_applied: list[str] = field(default_factory=list)
    blocked_fields: list[str] = field(default_factory=list)
    content_digest: str = ""
    fail_closed_reason: str | None = None
    allowed: bool = True


@dataclass
class EgressAuditRecord:
    channel: str
    destination: str
    policy_version: int
    decision: str  # allow | deny | failure
    transforms_applied: list[str]
    blocked_fields: list[str]
    content_digest: str
    correlation_id: str | None = None
    field_classes_summary: dict[str, int] = field(default_factory=dict)
