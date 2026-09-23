"""GreyNoise community IP context provider."""

from __future__ import annotations

from typing import Any

import httpx

from app.db.enums import ThreatIntelVerdict
from app.threat_intel.schemas import IntelLookupResult


class GreyNoiseProvider:
    name = "greynoise"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def lookup_ip(self, ip: str, client: httpx.AsyncClient) -> IntelLookupResult | None:
        response = await client.get(
            f"https://api.greynoise.io/v3/community/{ip}",
            headers={"key": self.api_key, "Accept": "application/json"},
        )
        if response.status_code in {404, 429}:
            return None
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        riot = bool(data.get("riot"))
        classification = str(data.get("classification") or "unknown").lower()

        if riot:
            verdict = ThreatIntelVerdict.CLEAN
            confidence = 0.85
        elif classification == "malicious":
            verdict = ThreatIntelVerdict.MALICIOUS
            confidence = 0.8
        elif classification == "benign":
            verdict = ThreatIntelVerdict.SUSPICIOUS
            confidence = 0.6
        else:
            verdict = ThreatIntelVerdict.UNKNOWN
            confidence = 0.3

        return IntelLookupResult(
            verdict=verdict,
            source=self.name,
            confidence=confidence,
            raw_response=data,
        )
