"""Sample / endpoint enrichment from alert hashes + threat-intel cache.

Third evidence path in the four-path model. Does NOT run sandboxes or invent
family labels — only stored alert fields and cached hash intel.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import InvestigationContext
from app.core.datetime_utils import as_naive_utc, utc_now
from app.db.enums import IocType
from app.models.entity import ThreatIntelEntry
from app.models.ingestion import Alert
from app.models.investigation import EventAlert
from app.skills.base import Skill, SkillResult

_HASH_RE = re.compile(r"^[a-fA-F0-9]{32}$|^[a-fA-F0-9]{40}$|^[a-fA-F0-9]{64}$")


def _hash_kind(value: str) -> str:
    n = len(value)
    if n == 32:
        return "md5"
    if n == 40:
        return "sha1"
    if n == 64:
        return "sha256"
    return "unknown"


class QuerySampleEnrichmentSkill(Skill):
    name = "query_sample_enrichment"
    description = (
        "Enrich file hashes / process names linked to the current event "
        "(sample & endpoint evidence path). Uses stored alert fields and hash "
        "threat-intel cache only — never invents sandbox or capa results."
    )

    @classmethod
    def parameters_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_hash": {
                    "type": "string",
                    "description": "Optional explicit hash (md5/sha1/sha256). Defaults to hashes on event alerts.",
                },
                "limit": {"type": "integer", "default": 10},
            },
            "required": [],
        }

    async def execute(
        self,
        params: dict[str, Any],
        ctx: InvestigationContext,
        session: AsyncSession,
    ) -> SkillResult:
        limit = min(int(params.get("limit") or 10), 20)
        explicit = str(params.get("file_hash") or "").strip().lower()

        event_alerts = await self._load_event_alerts(session, ctx.event.id)
        samples = self._collect_samples(event_alerts, explicit=explicit)[:limit]

        enriched: list[dict[str, Any]] = []
        for sample in samples:
            intel = await self._lookup_hash_intel(session, sample["file_hash"])
            enriched.append({**sample, "intel": intel})

        data = {
            "sample_count": len(enriched),
            "samples": enriched,
            "has_hash": any(s.get("file_hash") for s in enriched),
            "has_process": any(s.get("process_name") for s in enriched),
            "sandbox_available": False,
            "capa_available": False,
            "verification": {
                "rule": (
                    "Only stored alert hashes/processes and cached hash intel are returned. "
                    "Family labels / scores must come from intel.sources[]; "
                    "do not invent VirusTotal/capa/sandbox findings."
                ),
                "do_not": "Do not claim dynamic analysis when sandbox_available=false.",
            },
        }

        if not enriched:
            summary = (
                "No file_hash/process on linked alerts; sample path unavailable "
                "(do not invent sandbox results)."
            )
        else:
            hashed = sum(1 for s in enriched if s.get("file_hash"))
            malicious = sum(
                1
                for s in enriched
                if (s.get("intel") or {}).get("verdict") == "malicious"
            )
            summary = (
                f"Sample enrichment: {len(enriched)} endpoint clue(s), "
                f"{hashed} hash(es), malicious_hits={malicious}; sandbox=unavailable"
            )

        return SkillResult(
            success=True,
            summary=summary[:500],
            data=data,
            evidence_ref=f"sample:event:{ctx.event.id}",
        )

    @staticmethod
    async def _load_event_alerts(session: AsyncSession, event_id: Any) -> list[Alert]:
        result = await session.execute(
            select(Alert)
            .join(EventAlert, EventAlert.alert_id == Alert.id)
            .where(EventAlert.event_id == event_id)
            .order_by(Alert.occurred_at.asc())
            .limit(100)
        )
        return list(result.scalars().all())

    @staticmethod
    def _collect_samples(alerts: list[Alert], *, explicit: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        if explicit and _HASH_RE.match(explicit):
            key = f"hash:{explicit}"
            seen.add(key)
            rows.append(
                {
                    "file_hash": explicit,
                    "hash_type": _hash_kind(explicit),
                    "process_name": None,
                    "host_name": None,
                    "source_ref": "param:file_hash",
                    "alert_id": None,
                }
            )

        for alert in alerts:
            hash_val = (alert.file_hash or "").strip().lower() or None
            process = (alert.process_name or "").strip() or None
            if not hash_val and not process:
                continue
            if hash_val and not _HASH_RE.match(hash_val):
                hash_val = None
            if not hash_val and not process:
                continue
            key = f"hash:{hash_val}" if hash_val else f"proc:{process}:{alert.host_name}"
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "file_hash": hash_val,
                    "hash_type": _hash_kind(hash_val) if hash_val else None,
                    "process_name": process,
                    "host_name": alert.host_name,
                    "rule_name": alert.rule_name,
                    "occurred_at": as_naive_utc(alert.occurred_at).isoformat(),
                    "source_ref": f"alert:{alert.source_alert_id}",
                    "alert_id": str(alert.id),
                }
            )
        return rows

    @staticmethod
    async def _lookup_hash_intel(session: AsyncSession, file_hash: str | None) -> dict[str, Any]:
        if not file_hash:
            return {
                "verdict": "unknown",
                "sources": [],
                "conflicts": [],
                "note": "No hash to look up.",
            }
        now = as_naive_utc(utc_now())
        try:
            result = await session.execute(
                select(ThreatIntelEntry)
                .where(
                    ThreatIntelEntry.ioc_type == IocType.HASH,
                    ThreatIntelEntry.ioc_value == file_hash,
                    ThreatIntelEntry.expires_at >= now,
                )
                .order_by(ThreatIntelEntry.fetched_at.desc())
                .limit(8)
            )
        except SQLAlchemyError as exc:
            return {
                "verdict": "unknown",
                "sources": [],
                "conflicts": [],
                "note": f"Hash intel cache error: {exc}"[:200],
            }

        entries = list(result.scalars().all())
        if not entries:
            return {
                "verdict": "unknown",
                "sources": [],
                "conflicts": [],
                "note": "Hash not in threat-intel cache; treat as unknown only.",
            }

        sources = [
            {
                "source": e.source,
                "verdict": e.verdict.value,
                "confidence": e.confidence,
                "fetched_at": e.fetched_at.isoformat(),
            }
            for e in entries
        ]
        verdicts = {s["verdict"] for s in sources}
        conflicts = []
        if len(verdicts) > 1:
            conflicts.append(
                {
                    "field": "verdict",
                    "values": sorted(verdicts),
                    "note": "Hash intel sources disagree — verify platform原文.",
                }
            )
        rank = {"malicious": 0, "suspicious": 1, "clean": 2, "unknown": 3}
        primary = sorted(
            entries,
            key=lambda e: (rank.get(e.verdict.value, 9), -float(e.confidence or 0)),
        )[0]
        return {
            "verdict": primary.verdict.value,
            "source": primary.source,
            "confidence": primary.confidence,
            "sources": sources,
            "conflicts": conflicts,
        }
