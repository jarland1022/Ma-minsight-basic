"""Threat intel lookup skill (DB cache with multi-source aggregation)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import InvestigationContext
from app.core.datetime_utils import as_naive_utc, utc_now
from app.db.enums import IocType
from app.models.entity import ThreatIntelEntry
from app.skills.base import Skill, SkillResult

IOC_MAP = {
    "ip": IocType.IP,
    "domain": IocType.DOMAIN,
    "hash": IocType.HASH,
    "url": IocType.URL,
}


class QueryThreatIntelSkill(Skill):
    name = "query_threat_intel"
    description = (
        "Look up threat intelligence for an IOC (ip/domain/hash/url). "
        "Returns cached multi-source aggregation when available; never invent vendor scores."
    )

    @classmethod
    def parameters_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ioc_type": {"type": "string", "enum": ["ip", "domain", "hash", "url"]},
                "ioc_value": {"type": "string"},
            },
            "required": ["ioc_type", "ioc_value"],
        }

    async def execute(
        self,
        params: dict[str, Any],
        ctx: InvestigationContext,
        session: AsyncSession,
    ) -> SkillResult:
        ioc_type_str = str(params.get("ioc_type", "")).lower()
        ioc_value = str(params.get("ioc_value", "")).strip()
        ioc_type = IOC_MAP.get(ioc_type_str)
        if not ioc_type or not ioc_value:
            return SkillResult(success=False, summary="Invalid ioc_type or ioc_value", error="invalid_params")

        now = as_naive_utc(utc_now())
        try:
            result = await session.execute(
                select(ThreatIntelEntry)
                .where(
                    ThreatIntelEntry.ioc_type == ioc_type,
                    ThreatIntelEntry.ioc_value == ioc_value,
                    ThreatIntelEntry.expires_at >= now,
                )
                .order_by(ThreatIntelEntry.fetched_at.desc())
                .limit(8)
            )
        except SQLAlchemyError as exc:
            summary = f"Threat intel cache lookup failed for {ioc_type_str}:{ioc_value}: {exc}"
            return SkillResult(
                success=False,
                summary=summary[:500],
                data={
                    "verdict": "unknown",
                    "source": "cache_error",
                    "note": summary[:200],
                    "sources": [],
                    "conflicts": [],
                    "verification": _verification_note(),
                },
                evidence_ref=f"intel:{ioc_type_str}:{ioc_value}",
                error="cache_lookup_failed",
            )

        entries = list(result.scalars().all())
        if not entries:
            data = {
                "verdict": "unknown",
                "source": "not_configured",
                "confidence": 0.0,
                "sources": [],
                "conflicts": [],
                "note": "Threat intel provider not connected or cache miss; treat as unknown only.",
                "verification": _verification_note(),
            }
            summary = f"No intel for {ioc_type_str}:{ioc_value}; verdict=unknown (not configured)."
            return SkillResult(
                success=True,
                summary=summary,
                data=data,
                evidence_ref=f"intel:{ioc_type_str}:{ioc_value}",
            )

        sources: list[dict[str, Any]] = []
        for entry in entries:
            raw = entry.raw_response if isinstance(entry.raw_response, dict) else {}
            source_url = None
            for key in ("source_url", "permalink", "link", "url"):
                if isinstance(raw.get(key), str) and raw[key]:
                    source_url = raw[key]
                    break
            sources.append(
                {
                    "source": entry.source,
                    "verdict": entry.verdict.value,
                    "confidence": entry.confidence,
                    "fetched_at": entry.fetched_at.isoformat(),
                    "source_url": source_url,
                    "raw_keys": sorted(raw.keys())[:12],
                }
            )

        verdicts = {s["verdict"] for s in sources}
        conflicts: list[dict[str, Any]] = []
        if len(verdicts) > 1:
            conflicts.append(
                {
                    "field": "verdict",
                    "values": sorted(verdicts),
                    "note": "Sources disagree; do not majority-vote — verify in each platform原文.",
                }
            )

        # Prefer malicious > suspicious > clean > unknown, then higher confidence
        rank = {"malicious": 0, "suspicious": 1, "clean": 2, "unknown": 3}
        primary = sorted(
            entries,
            key=lambda e: (rank.get(e.verdict.value, 9), -float(e.confidence or 0)),
        )[0]

        data = {
            "verdict": primary.verdict.value,
            "source": primary.source,
            "confidence": primary.confidence,
            "fetched_at": primary.fetched_at.isoformat(),
            "sources": sources,
            "source_count": len(sources),
            "conflicts": conflicts,
            "aggregation": {
                "verdict_set": sorted(verdicts),
                "has_conflict": bool(conflicts),
                "primary_rule": "severity_then_confidence",
            },
            "verification": _verification_note(),
        }
        conflict_flag = " CONFLICT" if conflicts else ""
        summary = (
            f"Intel {ioc_type_str}:{ioc_value} verdict={primary.verdict.value} "
            f"sources={len(sources)}{conflict_flag} primary={primary.source}"
        )
        return SkillResult(
            success=True,
            summary=summary[:500],
            data=data,
            evidence_ref=f"intel:{ioc_type_str}:{ioc_value}",
        )


def _verification_note() -> dict[str, str]:
    return {
        "rule": "Critical scores/family labels must be checked against platform原文; AI paraphrase is not evidence.",
        "do_not": "Do not invent VirusTotal/微步/奇安信 scores or links absent from sources[].",
    }
