"""GreyNoise community IP context provider (via EgressGateway)."""

from __future__ import annotations

from typing import Any

from app.db.enums import ThreatIntelVerdict
from app.privacy.egress_gateway import EgressDeniedError, get_egress_gateway
from app.privacy.types import ContentType, EgressChannel, EgressContext
from app.threat_intel.schemas import IntelLookupResult


class GreyNoiseProvider:
    name = "greynoise"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def lookup_ip(self, ip: str, client: Any = None) -> IntelLookupResult | None:
        del client
        gateway = get_egress_gateway()
        # IP is path segment; TI channel allows public IP plaintext. Protect a stub for audit,
        # then send GET with channel enforcement (empty body).
        try:
            protected = await gateway.protect(
                channel=EgressChannel.TI,
                content_type=ContentType.QUERY_PARAMS,
                payload={"ipAddress": ip},
                context=EgressContext(),
            )
            if not protected.allowed:
                raise EgressDeniedError(protected.fail_closed_reason or "ti_protect_denied")
            # Public IP remains in path (TI analytic need); private blocked upstream / by protect.
            safe_ip = protected.payload.get("ipAddress", ip) if isinstance(protected.payload, dict) else ip
            if safe_ip in {"[PRIVATE_IP]", "[BLOCKED_UNKNOWN]"} or str(safe_ip).startswith("ip_"):
                return None
            response = await gateway.send(
                channel=EgressChannel.TI,
                method="GET",
                url=f"https://api.greynoise.io/v3/community/{safe_ip}",
                headers={"key": self.api_key, "Accept": "application/json"},
                content_type=ContentType.JSON,
                context=EgressContext(),
                timeout=30.0,
                protect_json=False,
            )
        except EgressDeniedError:
            raise
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
