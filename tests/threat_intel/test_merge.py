"""Tests for provider result merge logic."""

from app.db.enums import ThreatIntelVerdict
from app.threat_intel.merge import merge_lookup_results
from app.threat_intel.schemas import IntelLookupResult


def test_merge_prefers_malicious_over_clean() -> None:
    merged = merge_lookup_results(
        [
            IntelLookupResult(
                verdict=ThreatIntelVerdict.CLEAN,
                source="greynoise",
                confidence=0.85,
            ),
            IntelLookupResult(
                verdict=ThreatIntelVerdict.MALICIOUS,
                source="abuseipdb",
                confidence=0.9,
            ),
        ]
    )
    assert merged is not None
    assert merged.verdict == ThreatIntelVerdict.MALICIOUS
    assert merged.source == "abuseipdb,greynoise"
    assert merged.confidence == 0.9


def test_merge_empty_returns_none() -> None:
    assert merge_lookup_results([]) is None
