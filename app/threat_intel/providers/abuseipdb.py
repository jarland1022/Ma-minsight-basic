"""AbuseIPDB IP reputation provider."""

from __future__ import annotations

from typing import Any

import httpx

from app.db.enums import ThreatIntelVerdict
from app.threat_intel.schemas import IntelLookupResult


class AbuseIPDBProvider:
    name = "abuseipdb"

    def __init__(self, api_key: str, *, max_age_days: int = 90) -> None:
        self.api_key = api_key
        self.max_age_days = max_age_days

    async def lookup_ip(self, ip: str, client: httpx.AsyncClient) -> IntelLookupResult | None:
        response = await client.get(
            "https://api.abuseipdb.com/api/v2/check",
            headers={"Key": self.api_key, "Accept": "application/json"},
            params={"ipAddress": ip, "maxAgeInDays": self.max_age_days},
        )
        if response.status_code == 429:
            return None
        response.raise_for_status()
        data: dict[str, Any] = response.json().get("data") or {}
        score = int(data.get("abuseConfidenceScore") or 0)
        if score >= 75:
            verdict = ThreatIntelVerdict.MALICIOUS
        elif score >= 25:
            verdict = ThreatIntelVerdict.SUSPICIOUS
        elif score == 0:
            verdict = ThreatIntelVerdict.CLEAN
        else:
            verdict = ThreatIntelVerdict.UNKNOWN
        return IntelLookupResult(
            verdict=verdict,
            source=self.name,
            confidence=min(1.0, score / 100.0),
            raw_response=data,
        )
