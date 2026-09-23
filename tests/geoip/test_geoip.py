"""Tests for GeoIP lookup and enrichment."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from app.geoip.enrich import enrich_src_geo, format_src_geo_label
from app.geoip.lookup import GeoIpLookup
from app.ingestion.schemas.normalized_alert import NormalizedAlert


def test_format_src_geo_label() -> None:
    label = format_src_geo_label({"src_geo": {"country": "中国", "city": "上海"}})
    assert label == "中国 · 上海"


def test_enrich_src_geo_skips_private_ip() -> None:
    alert = NormalizedAlert(
        source_alert_id="a1",
        fingerprint="fp",
        occurred_at=datetime(2026, 6, 28, 10, 0, tzinfo=UTC),
        raw_data={},
        src_ip="10.0.0.1",
    )
    enrich_src_geo(alert)
    assert "src_geo" not in alert.normalized_fields


def test_enrich_src_geo_adds_location() -> None:
    alert = NormalizedAlert(
        source_alert_id="a1",
        fingerprint="fp",
        occurred_at=datetime(2026, 6, 28, 10, 0, tzinfo=UTC),
        raw_data={},
        src_ip="8.8.8.8",
    )
    with patch("app.geoip.enrich.get_geo_lookup") as get_lookup:
        lookup = MagicMock()
        lookup.lookup.return_value = {
            "country_code": "US",
            "country": "美国",
            "city": "Mountain View",
            "source": "geolite2",
        }
        get_lookup.return_value = lookup
        enrich_src_geo(alert)

    assert alert.normalized_fields["src_geo"]["country"] == "美国"


def test_lookup_returns_none_when_db_missing() -> None:
    lookup = GeoIpLookup(db_path="/tmp/does-not-exist.mmdb")
    assert lookup.lookup("8.8.8.8") is None
