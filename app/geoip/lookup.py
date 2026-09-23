"""MaxMind GeoLite2-City lookup."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import geoip2.database
import geoip2.errors

from app.core.config import settings
from app.threat_intel.ip_utils import is_public_ip

logger = logging.getLogger(__name__)

_reader: geoip2.database.Reader | None = None
_reader_path: str | None = None
_load_failed = False


def _localized_name(names: dict[str, str] | None, fallback: str | None) -> str | None:
    if not fallback:
        return None
    if not names:
        return fallback
    return names.get("zh-CN") or names.get("en") or fallback


class GeoIpLookup:
    """Resolve public IPs to country/city via GeoLite2-City.mmdb."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = (db_path or settings.geolite2_city_path or "").strip()

    @property
    def enabled(self) -> bool:
        return bool(self.db_path)

    @property
    def is_ready(self) -> bool:
        return self.enabled and Path(self.db_path).is_file()

    def lookup(self, ip: str | None) -> dict[str, Any] | None:
        if not ip or not is_public_ip(ip):
            return None

        reader = self._get_reader()
        if reader is None:
            return None

        try:
            response = reader.city(ip)
        except geoip2.errors.AddressNotFoundError:
            return None
        except geoip2.errors.GeoIP2Error as exc:
            logger.warning("GeoIP lookup failed for %s: %s", ip, exc)
            return None

        country_name = _localized_name(
            response.country.names,
            response.country.name,
        )
        city_name = _localized_name(
            response.city.names,
            response.city.name,
        )

        payload: dict[str, Any] = {
            "country_code": response.country.iso_code,
            "country": country_name,
            "city": city_name,
            "source": "geolite2",
        }
        return {key: value for key, value in payload.items() if value}

    def _get_reader(self) -> geoip2.database.Reader | None:
        global _reader, _reader_path, _load_failed

        if not self.is_ready:
            return None
        if _load_failed and _reader_path == self.db_path:
            return None
        if _reader is not None and _reader_path == self.db_path:
            return _reader

        try:
            _reader = geoip2.database.Reader(self.db_path)
            _reader_path = self.db_path
            _load_failed = False
            logger.info("GeoLite2 database loaded: %s", self.db_path)
        except Exception as exc:
            logger.error("Failed to load GeoLite2 database at %s: %s", self.db_path, exc)
            _reader = None
            _reader_path = self.db_path
            _load_failed = True
        return _reader


def get_geo_lookup() -> GeoIpLookup:
    return GeoIpLookup()
