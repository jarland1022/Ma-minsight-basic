"""Query asset profile, stats, memories, and on-duty knowledge."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import InvestigationContext
from app.core.datetime_utils import utc_now
from app.core.redis import get_redis
from app.db.enums import EntityType
from app.models.entity import EntityProfile, EntityProfileMemory, EntityProfileStat, OnDutyKnowledge
from app.skills.base import Skill, SkillResult

ENTITY_TYPE_MAP = {
    "ip": EntityType.IP,
    "host": EntityType.HOST,
    "user": EntityType.USER,
}

CACHE_TTL = 600


class QueryAssetSkill(Skill):
    name = "query_asset"
    description = (
        "Query structured asset context for an IP, host, or user: profile, 7-day stats, "
        "reference memories, and on-duty knowledge notes."
    )

    @classmethod
    def parameters_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "entity_type": {"type": "string", "enum": ["ip", "host", "user"]},
                "entity_key": {"type": "string"},
            },
            "required": ["entity_type", "entity_key"],
        }

    async def execute(
        self,
        params: dict[str, Any],
        ctx: InvestigationContext,
        session: AsyncSession,
    ) -> SkillResult:
        entity_type_str = str(params.get("entity_type", "")).lower()
        entity_key = str(params.get("entity_key", "")).strip()
        if entity_type_str not in ENTITY_TYPE_MAP or not entity_key:
            return SkillResult(
                success=False,
                summary="Invalid parameters: entity_type and entity_key required",
                error="invalid_params",
            )

        cache_key = f"asset:v1:{entity_type_str}:{entity_key.lower()}"
        cached = await self._read_cache(cache_key)
        if cached:
            return SkillResult(
                success=True,
                summary=cached["summary"],
                data=cached["data"],
                evidence_ref=f"asset:{entity_type_str}:{entity_key}",
                cache_key=cache_key,
            )

        entity_type = ENTITY_TYPE_MAP[entity_type_str]
        profile_result = await session.execute(
            select(EntityProfile).where(
                EntityProfile.entity_type == entity_type,
                EntityProfile.entity_key == entity_key,
            )
        )
        profile = profile_result.scalar_one_or_none()

        data: dict[str, Any] = {
            "entity_type": entity_type_str,
            "entity_key": entity_key,
            "profile": None,
            "stats_7d": None,
            "memories": [],
            "on_duty_notes": [],
            "reference_only": True,
        }

        if profile:
            data["profile"] = {
                "display_name": profile.display_name,
                "owner_team": profile.owner_team,
                "asset_criticality": profile.asset_criticality.value,
                "is_known_scanner": profile.is_known_scanner,
                "is_jump_host": profile.is_jump_host,
                "is_decommissioned": profile.is_decommissioned,
            }
            stats_result = await session.execute(
                select(EntityProfileStat).where(
                    EntityProfileStat.entity_profile_id == profile.id,
                    EntityProfileStat.window_days == 7,
                )
            )
            stats = stats_result.scalar_one_or_none()
            if stats:
                data["stats_7d"] = {
                    "alert_count": stats.alert_count,
                    "failed_login_count": stats.failed_login_count,
                    "external_conn_count": stats.external_conn_count,
                    "alert_by_category": stats.alert_by_category,
                }

            mem_result = await session.execute(
                select(EntityProfileMemory).where(EntityProfileMemory.entity_profile_id == profile.id)
            )
            now = utc_now()
            for mem in mem_result.scalars():
                if mem.valid_until and mem.valid_until < now:
                    continue
                data["memories"].append(
                    {
                        "type": mem.memory_type.value,
                        "content": mem.content,
                        "confidence": mem.confidence,
                        "reference_only": True,
                    }
                )

        notes = await self._match_on_duty(session, entity_type_str, entity_key)
        data["on_duty_notes"] = notes

        if profile:
            from app.entity.graph import one_hop_neighbors

            data["related_entities"] = await one_hop_neighbors(
                session, entity_type, entity_key, limit=8
            )

        if entity_type_str == "host":
            from app.tools.gateway.client import ToolGatewayClient

            gw = await ToolGatewayClient.invoke_optional(
                session,
                adapter="cmdb",
                operation="lookup_host",
                params={"host_name": entity_key},
            )
            if gw is not None:
                data["gateway_cmdb"] = gw.data

        summary = self._summarize(data)
        await self._write_cache(cache_key, summary, data)
        return SkillResult(
            success=True,
            summary=summary,
            data=data,
            evidence_ref=f"asset:{entity_type_str}:{entity_key}",
            cache_key=cache_key,
        )

    async def _match_on_duty(
        self,
        session: AsyncSession,
        entity_type: str,
        entity_key: str,
    ) -> list[str]:
        now = utc_now()
        result = await session.execute(select(OnDutyKnowledge).where(OnDutyKnowledge.is_active.is_(True)))
        notes: list[str] = []
        for item in result.scalars():
            if item.effective_from > now:
                continue
            if item.effective_until and item.effective_until < now:
                continue
            scope = item.scope or {}
            matched = False
            if entity_type in scope and str(scope.get(entity_type)) == entity_key:
                matched = True
            elif f"{entity_type}_name" in scope and str(scope.get(f"{entity_type}_name")) == entity_key:
                matched = True
            elif entity_key in scope.values():
                matched = True
            if matched:
                notes.append(item.content)
        return notes

    @staticmethod
    def _summarize(data: dict[str, Any]) -> str:
        if not data.get("profile"):
            notes = data.get("on_duty_notes") or []
            base = f"No profile for {data['entity_type']}:{data['entity_key']}."
            if notes:
                return base + f" On-duty notes: {'; '.join(notes[:2])}"
            return base
        profile = data["profile"]
        parts = [
            f"Asset {data['entity_key']}: criticality={profile.get('asset_criticality')},",
            f"scanner={profile.get('is_known_scanner')}, decommissioned={profile.get('is_decommissioned')}.",
        ]
        if data.get("stats_7d"):
            parts.append(f"7d alerts={data['stats_7d'].get('alert_count')}.")
        if data.get("on_duty_notes"):
            parts.append(f"On-duty: {data['on_duty_notes'][0][:120]}")
        related = data.get("related_entities") or []
        if related:
            rel_text = ", ".join(
                f"{r['relation_type']}->{r['entity_type']}:{r['entity_key']}" for r in related[:3]
            )
            parts.append(f"Related: {rel_text}.")
        return " ".join(parts)[:500]

    @staticmethod
    async def _read_cache(cache_key: str) -> dict[str, Any] | None:
        try:
            redis = await get_redis()
            raw = await redis.get(cache_key)
            if raw:
                return json.loads(raw)
        except Exception:
            return None
        return None

    @staticmethod
    async def _write_cache(cache_key: str, summary: str, data: dict[str, Any]) -> None:
        try:
            redis = await get_redis()
            await redis.set(
                cache_key,
                json.dumps({"summary": summary, "data": data}, ensure_ascii=False),
                ex=CACHE_TTL,
            )
        except Exception:
            pass
