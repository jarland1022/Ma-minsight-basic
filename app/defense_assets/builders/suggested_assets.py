"""Parse investigation_conclusions.suggested_assets into candidate rows."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import CandidateStatus, InvestigationVerdict, ProfileUpdateStatus
from app.defense_assets.config import DefenseAssetConfig
from app.models.defense_assets import ProfileUpdateSuggestion, RuleCandidate
from app.models.entity import EntityProfile, EntityType
from app.models.investigation import InvestigationConclusion
from app.models.triage import WhitelistCandidate, WhitelistCandidateStatus


def pattern_hash(match_pattern: dict[str, Any]) -> str:
    canonical = json.dumps(match_pattern, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def extract_match_pattern(suggested: dict[str, Any]) -> dict[str, Any] | None:
    if "match_pattern" in suggested:
        mp = suggested["match_pattern"]
        return mp if isinstance(mp, dict) else None
    if "field" in suggested and "value" in suggested:
        return suggested
    return None


async def create_whitelist_candidate_if_applicable(
    session: AsyncSession,
    *,
    investigation_id: UUID,
    conclusion: InvestigationConclusion,
    config: DefenseAssetConfig,
) -> WhitelistCandidate | None:
    if config.create_whitelist_on_fp_only and conclusion.verdict != InvestigationVerdict.LIKELY_FALSE_POSITIVE:
        return None

    suggested_assets = conclusion.suggested_assets or {}
    if not isinstance(suggested_assets, dict):
        return None
    wl = suggested_assets.get("whitelist_candidate")
    if not isinstance(wl, dict):
        return None

    match_pattern = extract_match_pattern(wl)
    if match_pattern is None:
        return None

    phash = pattern_hash(match_pattern)
    from sqlalchemy import select

    existing = await session.execute(
        select(WhitelistCandidate).where(
            WhitelistCandidate.status == WhitelistCandidateStatus.PENDING,
            WhitelistCandidate.suggested_pattern.contains({"pattern_hash": phash}),
        )
    )
    if existing.scalar_one_or_none() is not None:
        return None

    payload = {
        "rule_type": wl.get("rule_type", "composite"),
        "match_pattern": match_pattern,
        "pattern_hash": phash,
    }
    return WhitelistCandidate(
        investigation_id=investigation_id,
        suggested_pattern=payload,
        reason=wl.get("reason"),
    )


async def create_profile_suggestion_if_applicable(
    session: AsyncSession,
    *,
    investigation_id: UUID,
    conclusion: InvestigationConclusion,
) -> ProfileUpdateSuggestion | None:
    suggested_assets = conclusion.suggested_assets or {}
    if not isinstance(suggested_assets, dict):
        return None
    pu = suggested_assets.get("profile_update")
    if not isinstance(pu, dict):
        return None

    entity_type_raw = pu.get("entity_type", "host")
    entity_key = pu.get("entity_key")
    if not entity_key:
        return None

    try:
        entity_type = EntityType(str(entity_type_raw))
    except ValueError:
        entity_type = EntityType.HOST

    from sqlalchemy import select

    profile_result = await session.execute(
        select(EntityProfile).where(
            EntityProfile.entity_type == entity_type,
            EntityProfile.entity_key == str(entity_key),
        )
    )
    profile = profile_result.scalar_one_or_none()
    if profile is None:
        profile = EntityProfile(entity_type=entity_type, entity_key=str(entity_key))
        session.add(profile)
        await session.flush()

    return ProfileUpdateSuggestion(
        investigation_id=investigation_id,
        entity_profile_id=profile.id,
        suggested_changes=pu,
        status=ProfileUpdateStatus.PENDING,
    )


async def create_rule_candidate_if_applicable(
    session: AsyncSession,
    *,
    investigation_id: UUID,
    conclusion: InvestigationConclusion,
) -> RuleCandidate | None:
    suggested_assets = conclusion.suggested_assets or {}
    if not isinstance(suggested_assets, dict):
        return None
    rc = suggested_assets.get("rule_candidate")
    if not isinstance(rc, dict):
        return None

    return RuleCandidate(
        investigation_id=investigation_id,
        rule_draft=rc,
        reason=rc.get("reason"),
        status=CandidateStatus.PENDING,
    )
