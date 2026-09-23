"""Normalized alert DTO — ingestion layer contract before DB persist."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NormalizedAlert(BaseModel):
    source_alert_id: str
    fingerprint: str
    rule_id: str | None = None
    rule_name: str | None = None
    severity: int = Field(ge=1, le=5, default=3)
    severity_raw: str | None = None
    occurred_at: datetime
    src_ip: str | None = None
    dst_ip: str | None = None
    src_port: int | None = None
    dst_port: int | None = None
    user_name: str | None = None
    host_name: str | None = None
    process_name: str | None = None
    process_cmdline: str | None = None
    file_hash: str | None = None
    alert_category: str | None = None
    normalized_fields: dict[str, Any] = Field(default_factory=dict)
    raw_data: dict[str, Any]
