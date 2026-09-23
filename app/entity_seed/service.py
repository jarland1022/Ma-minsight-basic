"""Seed entity_profiles and on_duty_knowledge via ORM (enum-safe)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now
from app.db.enums import AssetCriticality, EntityType
from app.entity_seed.data import DEFAULT_ASSETS, SCANNER_IP, SCANNER_NOTE
from app.models.entity import EntityProfile, EntityRelation, OnDutyKnowledge

logger = logging.getLogger(__name__)


@dataclass
class EntitySeedResult:
    profiles_upserted: int = 0
    on_duty_upserted: int = 0
    relations_upserted: int = 0
    errors: list[str] = field(default_factory=list)


async def seed_entity_assets(session: AsyncSession) -> EntitySeedResult:
    result = EntitySeedResult()
    now = utc_now()

    for asset in DEFAULT_ASSETS:
        host_meta = {
            "public_ip": asset.public_ip,
            "private_ip": asset.private_ip,
            "app": asset.display_name,
            **asset.extra_metadata,
        }
        await _upsert_profile(
            session,
            entity_type=EntityType.HOST,
            entity_key=asset.host,
            display_name=asset.display_name,
            owner_team=asset.owner_team,
            criticality=asset.criticality,
            is_jump_host=asset.is_jump_host,
            metadata=host_meta,
            result=result,
        )
        await _upsert_profile(
            session,
            entity_type=EntityType.IP,
            entity_key=asset.public_ip,
            display_name=f"{asset.display_name}-公网",
            owner_team=asset.owner_team,
            criticality=asset.criticality,
            is_jump_host=asset.is_jump_host,
            metadata={"host": asset.host, "private_ip": asset.private_ip, **asset.extra_metadata},
            result=result,
        )
        await _upsert_profile(
            session,
            entity_type=EntityType.IP,
            entity_key=asset.private_ip,
            display_name=f"{asset.display_name}-内网",
            owner_team=asset.owner_team,
            criticality=asset.criticality,
            is_jump_host=asset.is_jump_host,
            metadata={"host": asset.host, "public_ip": asset.public_ip, **asset.extra_metadata},
            result=result,
        )

    await _upsert_profile(
        session,
        entity_type=EntityType.IP,
        entity_key=SCANNER_IP,
        display_name="等保漏扫器",
        owner_team="安全",
        criticality=AssetCriticality.LOW,
        is_known_scanner=True,
        metadata={"type": "compliance_scanner", "note": SCANNER_NOTE},
        result=result,
    )

    title = "等保测评漏洞扫描器"
    existing = await session.execute(
        select(OnDutyKnowledge).where(OnDutyKnowledge.title == title).limit(1)
    )
    knowledge = existing.scalar_one_or_none()
    if knowledge is None:
        session.add(
            OnDutyKnowledge(
                title=title,
                scope={"src_ip": SCANNER_IP},
                content=SCANNER_NOTE,
                effective_from=now,
                effective_until=None,
                is_active=True,
            )
        )
        result.on_duty_upserted += 1
    else:
        knowledge.scope = {"src_ip": SCANNER_IP}
        knowledge.content = SCANNER_NOTE
        knowledge.is_active = True
        result.on_duty_upserted += 1

    for asset in DEFAULT_ASSETS:
        await _upsert_relation(
            session,
            EntityType.HOST,
            asset.host,
            EntityType.IP,
            asset.public_ip,
            "has_public_ip",
            result,
        )
        await _upsert_relation(
            session,
            EntityType.HOST,
            asset.host,
            EntityType.IP,
            asset.private_ip,
            "has_private_ip",
            result,
        )

    await _upsert_relation(
        session,
        EntityType.IP,
        SCANNER_IP,
        EntityType.HOST,
        "waf",
        "scanner_source",
        result,
        metadata={"note": SCANNER_NOTE},
    )

    await session.commit()
    return result


async def _upsert_profile(
    session: AsyncSession,
    *,
    entity_type: EntityType,
    entity_key: str,
    display_name: str,
    owner_team: str,
    criticality: AssetCriticality,
    metadata: dict,
    result: EntitySeedResult,
    is_known_scanner: bool = False,
    is_jump_host: bool = False,
) -> None:
    row = await session.execute(
        select(EntityProfile).where(
            EntityProfile.entity_type == entity_type,
            EntityProfile.entity_key == entity_key,
        )
    )
    profile = row.scalar_one_or_none()
    if profile is None:
        session.add(
            EntityProfile(
                entity_type=entity_type,
                entity_key=entity_key,
                display_name=display_name,
                owner_team=owner_team,
                asset_criticality=criticality,
                is_known_scanner=is_known_scanner,
                is_jump_host=is_jump_host,
                is_decommissioned=False,
                metadata_=metadata,
            )
        )
    else:
        profile.display_name = display_name
        profile.owner_team = owner_team
        profile.asset_criticality = criticality
        profile.is_known_scanner = is_known_scanner
        profile.is_jump_host = is_jump_host
        profile.metadata_ = metadata
    result.profiles_upserted += 1


async def _upsert_relation(
    session: AsyncSession,
    from_type: EntityType,
    from_key: str,
    to_type: EntityType,
    to_key: str,
    relation_type: str,
    result: EntitySeedResult,
    *,
    metadata: dict | None = None,
) -> None:
    row = await session.execute(
        select(EntityRelation).where(
            EntityRelation.from_entity_type == from_type,
            EntityRelation.from_entity_key == from_key,
            EntityRelation.to_entity_type == to_type,
            EntityRelation.to_entity_key == to_key,
            EntityRelation.relation_type == relation_type,
        )
    )
    rel = row.scalar_one_or_none()
    if rel is None:
        session.add(
            EntityRelation(
                from_entity_type=from_type,
                from_entity_key=from_key,
                to_entity_type=to_type,
                to_entity_key=to_key,
                relation_type=relation_type,
                confidence=1.0,
                source="seed",
                metadata_=metadata or {},
            )
        )
    else:
        rel.metadata_ = metadata or rel.metadata_ or {}
    result.relations_upserted += 1
