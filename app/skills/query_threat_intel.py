"""Threat intel lookup skill (stub with DB cache)."""

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
    description = "Look up threat intelligence for an IOC (ip/domain/hash/url). Returns cached intel or unknown."

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
                .limit(1)
            )
        except SQLAlchemyError as exc:
            summary = f"Threat intel cache lookup failed for {ioc_type_str}:{ioc_value}: {exc}"
            return SkillResult(
                success=False,
                summary=summary[:500],
                data={"verdict": "unknown", "source": "cache_error", "note": summary[:200]},
                evidence_ref=f"intel:{ioc_type_str}:{ioc_value}",
                error="cache_lookup_failed",
            )
        entry = result.scalar_one_or_none()
        if entry:
            data = {
                "verdict": entry.verdict.value,
                "source": entry.source,
                "confidence": entry.confidence,
                "fetched_at": entry.fetched_at.isoformat(),
            }
            summary = f"Intel {ioc_type_str}:{ioc_value} verdict={entry.verdict.value} source={entry.source}"
            return SkillResult(
                success=True,
                summary=summary[:500],
                data=data,
                evidence_ref=f"intel:{ioc_type_str}:{ioc_value}",
            )

        data = {
            "verdict": "unknown",
            "source": "not_configured",
            "note": "Threat intel provider not connected; treat as unknown only.",
        }
        summary = f"No intel for {ioc_type_str}:{ioc_value}; verdict=unknown (not configured)."
        return SkillResult(
            success=True,
            summary=summary,
            data=data,
            evidence_ref=f"intel:{ioc_type_str}:{ioc_value}",
        )
