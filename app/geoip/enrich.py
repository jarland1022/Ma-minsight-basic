"""Enrich normalized alerts with GeoIP metadata."""

from __future__ import annotations

from typing import Any

from app.geoip.lookup import get_geo_lookup
from app.ingestion.schemas.normalized_alert import NormalizedAlert


def format_src_geo_label(normalized_fields: dict[str, Any] | None) -> str | None:
    if not normalized_fields:
        return None
    geo = normalized_fields.get("src_geo")
    if not isinstance(geo, dict):
        return None

    country = geo.get("country") or geo.get("country_code")
    city = geo.get("city")
    parts = [part for part in (country, city) if part]
    return " · ".join(str(part) for part in parts) if parts else None


def enrich_src_geo(normalized: NormalizedAlert) -> None:
    """Attach src_geo to normalized_fields when GeoLite2 is configured."""
    if not normalized.src_ip:
        return
    if isinstance(normalized.normalized_fields.get("src_geo"), dict):
        return

    geo = get_geo_lookup().lookup(normalized.src_ip)
    if not geo:
        return

    fields = dict(normalized.normalized_fields)
    fields["src_geo"] = geo
    normalized.normalized_fields = fields
