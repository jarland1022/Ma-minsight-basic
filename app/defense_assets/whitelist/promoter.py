"""Promote whitelist candidates to active rules after threshold confirmations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import WhitelistRuleStatus, WhitelistRuleType
from app.defense_assets.builders.suggested_assets import pattern_hash
from app.defense_assets.config import DefenseAssetConfig
from app.models.triage import WhitelistCandidate, WhitelistCandidateStatus, WhitelistRule


class WhitelistPromoter:
    def __init__(self, session: AsyncSession, config: DefenseAssetConfig) -> None:
        self.session = session
        self.config = config

    async def confirm_candidate(self, candidate_id: UUID) -> WhitelistRule | None:
        candidate = await self.session.get(WhitelistCandidate, candidate_id)
        if candidate is None or candidate.status != WhitelistCandidateStatus.PENDING:
            return None

        candidate.human_confirmations += 1
        if candidate.human_confirmations < self.config.whitelist_promotion_threshold:
            await self.session.flush()
            return None

        return await self._promote(candidate)

    async def reject_candidate(self, candidate_id: UUID) -> bool:
        candidate = await self.session.get(WhitelistCandidate, candidate_id)
        if candidate is None or candidate.status != WhitelistCandidateStatus.PENDING:
            return False
        candidate.status = WhitelistCandidateStatus.REJECTED
        return True

    async def _promote(self, candidate: WhitelistCandidate) -> WhitelistRule:
        pattern = candidate.suggested_pattern or {}
        match_pattern = pattern.get("match_pattern") or {}
        rule_type_raw = pattern.get("rule_type", "composite")
        try:
            rule_type = WhitelistRuleType(str(rule_type_raw))
        except ValueError:
            rule_type = WhitelistRuleType.COMPOSITE

        phash = pattern.get("pattern_hash") or pattern_hash(match_pattern)
        now = datetime.now(UTC)
        rule = WhitelistRule(
            name=f"auto-promoted-{phash}",
            rule_type=rule_type,
            match_pattern=match_pattern,
            confirmation_count=candidate.human_confirmations,
            effective_from=now,
            effective_until=now + timedelta(days=self.config.whitelist_rule_ttl_days),
            status=WhitelistRuleStatus.ACTIVE,
            audit_trail=[
                {
                    "source": "whitelist_candidate",
                    "candidate_id": str(candidate.id),
                    "investigation_id": str(candidate.investigation_id),
                    "confirmations": candidate.human_confirmations,
                }
            ],
        )
        self.session.add(rule)
        await self.session.flush()

        candidate.status = WhitelistCandidateStatus.PROMOTED
        candidate.promoted_rule_id = rule.id
        return rule
