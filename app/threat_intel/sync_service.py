"""Sync external threat intel into threat_intel_entries."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.datetime_utils import as_naive_utc, utc_now
from app.db.enums import IocType
from app.models.entity import ThreatIntelEntry
from app.models.ingestion import Alert
from app.threat_intel.ip_utils import is_public_ip, normalize_ip
from app.threat_intel.merge import merge_lookup_results
from app.threat_intel.providers.abuseipdb import AbuseIPDBProvider
from app.threat_intel.providers.greynoise import GreyNoiseProvider
from app.threat_intel.schemas import IntelLookupResult

logger = logging.getLogger(__name__)


class _Provider(Protocol):
    name: str

    async def lookup_ip(self, ip: str, client: httpx.AsyncClient) -> IntelLookupResult | None: ...


@dataclass
class ThreatIntelSyncResult:
    candidates: int = 0
    skipped_private: int = 0
    skipped_fresh: int = 0
    synced: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


class ThreatIntelSyncService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(
        self,
        *,
        window_days: int | None = None,
        limit: int | None = None,
        force: bool = False,
        dry_run: bool = False,
        ips: list[str] | None = None,
    ) -> ThreatIntelSyncResult:
        result = ThreatIntelSyncResult()
        providers = self._build_providers()
        if not providers:
            result.errors.append("No threat intel provider configured (set ABUSEIPDB_API_KEY or GREYNOISE_API_KEY)")
            return result

        window_days = window_days if window_days is not None else settings.threat_intel_sync_window_days
        limit = limit if limit is not None else settings.threat_intel_sync_limit
        target_ips = ips if ips is not None else await self._collect_alert_ips(window_days=window_days, limit=limit)
        result.candidates = len(target_ips)

        cache_ttl = timedelta(hours=settings.threat_intel_cache_ttl_hours)
        now = as_naive_utc(utc_now())
        expires_at = now + cache_ttl

        async with httpx.AsyncClient(timeout=settings.threat_intel_http_timeout_seconds) as client:
            for raw_ip in target_ips:
                ip = normalize_ip(raw_ip)
                if ip is None:
                    continue
                if settings.threat_intel_skip_private_ips and not is_public_ip(ip):
                    result.skipped_private += 1
                    continue
                if not force and await self._has_fresh_cache(ip, now=now):
                    result.skipped_fresh += 1
                    continue

                lookup_results: list[IntelLookupResult] = []
                for provider in providers:
                    try:
                        item = await provider.lookup_ip(ip, client)
                        if item is not None:
                            lookup_results.append(item)
                    except httpx.HTTPStatusError as exc:
                        result.failed += 1
                        result.errors.append(f"{provider.name}:{ip}: HTTP {exc.response.status_code}")
                        logger.warning("Provider %s failed for %s", provider.name, ip, exc_info=True)
                    except Exception as exc:
                        result.failed += 1
                        result.errors.append(f"{provider.name}:{ip}: {exc}")
                        logger.exception("Provider %s failed for %s", provider.name, ip)

                merged = merge_lookup_results(lookup_results)
                if merged is None:
                    continue
                if dry_run:
                    logger.info(
                        "DRY RUN ip=%s verdict=%s source=%s confidence=%.2f",
                        ip,
                        merged.verdict.value,
                        merged.source,
                        merged.confidence,
                    )
                    result.synced += 1
                    continue

                self.session.add(
                    ThreatIntelEntry(
                        ioc_type=IocType.IP,
                        ioc_value=ip,
                        verdict=merged.verdict,
                        source=merged.source,
                        confidence=merged.confidence,
                        raw_response=merged.raw_response,
                        fetched_at=now,
                        expires_at=expires_at,
                    )
                )
                result.synced += 1

        if result.synced and not dry_run:
            await self.session.commit()
        return result

    @staticmethod
    def _build_providers() -> list[_Provider]:
        providers: list[_Provider] = []
        if settings.greynoise_api_key:
            providers.append(GreyNoiseProvider(settings.greynoise_api_key))
        if settings.abuseipdb_api_key:
            providers.append(
                AbuseIPDBProvider(
                    settings.abuseipdb_api_key,
                    max_age_days=settings.abuseipdb_max_age_days,
                )
            )
        return providers

    async def _collect_alert_ips(self, *, window_days: int, limit: int) -> list[str]:
        since = utc_now() - timedelta(days=window_days)
        stmt = (
            select(Alert.src_ip)
            .where(Alert.src_ip.isnot(None), Alert.occurred_at >= since)
            .distinct()
            .limit(limit)
        )
        rows = await self.session.execute(stmt)
        return [str(row[0]) for row in rows.all() if row[0] is not None]

    async def _has_fresh_cache(self, ip: str, *, now) -> bool:
        stmt = (
            select(ThreatIntelEntry.id)
            .where(
                ThreatIntelEntry.ioc_type == IocType.IP,
                ThreatIntelEntry.ioc_value == ip,
                ThreatIntelEntry.expires_at >= now,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
