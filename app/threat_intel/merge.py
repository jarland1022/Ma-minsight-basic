"""Merge provider lookup results into a single cache row."""

from __future__ import annotations

from app.db.enums import ThreatIntelVerdict
from app.threat_intel.schemas import IntelLookupResult

_VERDICT_RANK = {
    ThreatIntelVerdict.CLEAN: 1,
    ThreatIntelVerdict.UNKNOWN: 2,
    ThreatIntelVerdict.SUSPICIOUS: 3,
    ThreatIntelVerdict.MALICIOUS: 4,
}


def merge_lookup_results(results: list[IntelLookupResult]) -> IntelLookupResult | None:
    if not results:
        return None

    best = max(results, key=lambda item: (_VERDICT_RANK[item.verdict], item.confidence))
    sources = sorted({item.source for item in results})
    raw_response = {item.source: item.raw_response for item in results}
    confidence = max(item.confidence for item in results if item.verdict == best.verdict)
    return IntelLookupResult(
        verdict=best.verdict,
        source=",".join(sources),
        confidence=confidence,
        raw_response=raw_response,
    )
