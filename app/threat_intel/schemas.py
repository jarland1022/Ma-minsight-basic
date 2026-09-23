"""Shared types for threat intel provider results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.db.enums import ThreatIntelVerdict


@dataclass
class IntelLookupResult:
    verdict: ThreatIntelVerdict
    source: str
    confidence: float
    raw_response: dict[str, Any] = field(default_factory=dict)
