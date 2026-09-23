"""Asset sedimentation pipeline for concluded events."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import (
    ActorType,
    DispositionStatus,
    EventStatus,
    InvestigationStatus,
    InvestigationVerdict,
)
from app.defense_assets.builders.judgment_case import build_judgment_case
from app.defense_assets.builders.suggested_assets import (
    create_profile_suggestion_if_applicable,
    create_rule_candidate_if_applicable,
    create_whitelist_candidate_if_applicable,
)
from app.defense_assets.config import DefenseAssetConfig, load_defense_asset_config
from app.defense_assets.embedding import EmbeddingService
from app.eval.probe.guard import event_is_probe
from app.defense_assets.lock import defense_asset_lock
from app.models.defense_assets import DispositionRecord, JudgmentCase
from app.models.investigation import Event, Investigation, InvestigationConclusion
from app.models.system import AuditLog

logger = logging.getLogger(__name__)

SETTLE_VERDICTS = (
    InvestigationVerdict.ATTACK_CONFIRMED,
    InvestigationVerdict.LIKELY_FALSE_POSITIVE,
)


@dataclass
class AssetPipelineResult:
    processed: int = 0
    skipped_lock: bool = False
    skipped_disabled: bool = False
    errors: list[str] = field(default_factory=list)


class AssetPipeline:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(self, *, limit: int | None = None, use_lock: bool = True) -> AssetPipelineResult:
        result = AssetPipelineResult()

        async def _execute() -> AssetPipelineResult:
            config = await load_defense_asset_config(self.session)
            if not config.enabled:
                result.skipped_disabled = True
                return result

            batch = limit or config.batch_size
            targets = await self._pick_targets(batch)
            embedder = EmbeddingService(model=config.embedding_model)

            for event, investigation, conclusion in targets:
                try:
                    await self._settle_one(event, investigation, conclusion, config, embedder)
                    result.processed += 1
                except Exception as exc:
                    result.errors.append(f"{event.id}: {exc}")
                    logger.exception("Asset pipeline failed for event=%s", event.id)

            if result.processed:
                self.session.add(
                    AuditLog(
                        actor_type=ActorType.SYSTEM,
                        action="defense_assets.batch_completed",
                        resource_type="defense_assets",
                        resource_id="global",
                        detail={"processed": result.processed, "errors": len(result.errors)},
                    )
                )
            await self.session.commit()
            return result

        if use_lock:
            async with defense_asset_lock() as acquired:
                if not acquired:
                    result.skipped_lock = True
                    return result
                return await _execute()
        return await _execute()

    async def stats(self) -> dict[str, int]:
        from sqlalchemy import func

        pending_events = await self.session.execute(
            select(func.count())
            .select_from(Event)
            .where(Event.status == EventStatus.CONCLUDED)
        )
        judgment_count = await self.session.execute(select(func.count()).select_from(JudgmentCase))
        suggested_disp = await self.session.execute(
            select(func.count())
            .select_from(DispositionRecord)
            .where(DispositionRecord.status == DispositionStatus.SUGGESTED)
        )
        return {
            "concluded_events": int(pending_events.scalar_one() or 0),
            "judgment_cases": int(judgment_count.scalar_one() or 0),
            "disposition_suggested": int(suggested_disp.scalar_one() or 0),
        }

    async def _pick_targets(
        self, limit: int
    ) -> list[tuple[Event, Investigation, InvestigationConclusion]]:
        stmt = (
            select(Event)
            .where(Event.status == EventStatus.CONCLUDED)
            .order_by(Event.last_alert_at.asc())
            .limit(limit * 3)
        )
        events = list((await self.session.execute(stmt)).scalars().all())
        targets: list[tuple[Event, Investigation, InvestigationConclusion]] = []

        for event in events:
            if len(targets) >= limit:
                break
            if await event_is_probe(self.session, event.id):
                continue
            inv_conc = await self._latest_settleable_investigation(event.id)
            if inv_conc is None:
                continue
            investigation, conclusion = inv_conc
            existing = await self.session.execute(
                select(JudgmentCase.id).where(JudgmentCase.investigation_id == investigation.id)
            )
            if existing.scalar_one_or_none() is not None:
                if await self._should_close_event(event.id, investigation.id):
                    event.status = EventStatus.CLOSED
                continue
            targets.append((event, investigation, conclusion))
        return targets

    async def _latest_settleable_investigation(
        self, event_id: UUID
    ) -> tuple[Investigation, InvestigationConclusion] | None:
        stmt = (
            select(Investigation)
            .options(selectinload(Investigation.conclusion))
            .where(
                Investigation.event_id == event_id,
                Investigation.status == InvestigationStatus.COMPLETED,
            )
            .order_by(Investigation.finished_at.desc().nullslast(), Investigation.started_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        investigation = result.scalar_one_or_none()
        if investigation is None or investigation.conclusion is None:
            return None
        if investigation.conclusion.verdict not in SETTLE_VERDICTS:
            return None
        return investigation, investigation.conclusion

    async def _settle_one(
        self,
        event: Event,
        investigation: Investigation,
        conclusion: InvestigationConclusion,
        config: DefenseAssetConfig,
        embedder: EmbeddingService,
    ) -> None:
        case = await build_judgment_case(
            self.session,
            investigation=investigation,
            event=event,
            conclusion=conclusion,
        )
        if config.embedding_enabled:
            vector = await embedder.embed(case.feature_summary)
            if vector is not None:
                case.embedding = vector

        self.session.add(case)

        wl = await create_whitelist_candidate_if_applicable(
            self.session,
            investigation_id=investigation.id,
            conclusion=conclusion,
            config=config,
        )
        if wl is not None:
            self.session.add(wl)

        profile = await create_profile_suggestion_if_applicable(
            self.session,
            investigation_id=investigation.id,
            conclusion=conclusion,
        )
        if profile is not None:
            self.session.add(profile)

        rule = await create_rule_candidate_if_applicable(
            self.session,
            investigation_id=investigation.id,
            conclusion=conclusion,
        )
        if rule is not None:
            self.session.add(rule)

        if config.auto_close_event and not config.require_disposition_confirm:
            event.status = EventStatus.CLOSED
        elif config.auto_close_event and config.require_disposition_confirm:
            if await self._dispositions_resolved(investigation.id):
                event.status = EventStatus.CLOSED

    async def _dispositions_resolved(self, investigation_id: UUID) -> bool:
        result = await self.session.execute(
            select(DispositionRecord).where(DispositionRecord.investigation_id == investigation_id)
        )
        records = list(result.scalars().all())
        if not records:
            return True
        return all(r.status != DispositionStatus.SUGGESTED for r in records)

    async def _should_close_event(self, event_id: UUID, investigation_id: UUID) -> bool:
        config = await load_defense_asset_config(self.session)
        if not config.auto_close_event:
            return False
        if config.require_disposition_confirm:
            return await self._dispositions_resolved(investigation_id)
        return True
