"""Investigation orchestration: pick events, run Agent, persist outcomes."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now

from app.agent.budget import budget_remaining, increment_daily_count
from app.agent.config import InvestigationConfig, load_investigation_config
from app.agent.context_builder import build_investigation_context
from app.entity.graph import build_event_entity_context_snapshot
from app.agent.conclusion import ConclusionPayload, degraded_conclusion
from app.agent.lock import investigate_lock
from app.agent.loop import AgentLoop
from app.human_review.reinvestigation import consume_skip_budget
from app.eval.probe.guard import event_is_probe, probe_event_ids_subquery
from app.db.enums import (
    ActorType,
    DispositionStatus,
    EventStatus,
    InvestigationStatus,
    InvestigationVerdict,
)
from app.models.defense_assets import DispositionRecord
from app.agent.supervisor import InvestigationSupervisor, SupervisorConfig
from app.human_review.stale import cancel_obsolete_sent_reviews_for_event
from app.models.investigation import Event, Investigation, InvestigationAudit, InvestigationConclusion
from app.models.system import AuditLog

logger = logging.getLogger(__name__)

VERDICT_EVENT_STATUS = {
    InvestigationVerdict.ATTACK_CONFIRMED: EventStatus.CONCLUDED,
    InvestigationVerdict.LIKELY_FALSE_POSITIVE: EventStatus.CONCLUDED,
    InvestigationVerdict.INSUFFICIENT_INFORMATION: EventStatus.HUMAN_PENDING,
    InvestigationVerdict.NEEDS_HUMAN_REVIEW: EventStatus.HUMAN_PENDING,
}


@dataclass
class InvestigationRunResult:
    processed: int = 0
    skipped_lock: bool = False
    skipped_budget: bool = False
    errors: list[str] = field(default_factory=list)


class InvestigationOrchestrator:
    def __init__(self, session: AsyncSession, agent: AgentLoop | None = None) -> None:
        self.session = session
        self.agent = agent or AgentLoop()

    async def run(self, *, limit: int | None = None, use_lock: bool = True) -> InvestigationRunResult:
        result = InvestigationRunResult()

        async def _execute() -> InvestigationRunResult:
            config = await load_investigation_config(self.session)
            remaining = await budget_remaining(config.daily_event_budget)
            if remaining <= 0:
                result.skipped_budget = True
                return result

            batch = min(limit or config.batch_size, remaining)
            events = await self._pick_events(batch)
            for event in events:
                try:
                    await self._investigate_event(event, config)
                    if not await event_is_probe(self.session, event.id):
                        if not await consume_skip_budget(event.id):
                            await increment_daily_count()
                    await self.session.commit()
                    result.processed += 1
                except Exception as exc:
                    await self.session.rollback()
                    result.errors.append(f"{event.id}: {exc}")
                    logger.exception("Investigation failed for event=%s", event.id)

            if result.processed:
                self.session.add(
                    AuditLog(
                        actor_type=ActorType.SYSTEM,
                        action="investigation.batch_completed",
                        resource_type="investigation",
                        resource_id="global",
                        detail={"processed": result.processed, "errors": len(result.errors)},
                    )
                )
                await self.session.commit()
            return result

        if use_lock:
            async with investigate_lock() as acquired:
                if not acquired:
                    result.skipped_lock = True
                    return result
                return await _execute()
        return await _execute()

    async def get_investigation_detail(self, investigation_id: UUID) -> dict | None:
        inv = await self.session.get(Investigation, investigation_id)
        if inv is None:
            return None
        await self.session.refresh(inv, ["tool_calls", "messages", "conclusion"])
        return {
            "id": str(inv.id),
            "event_id": str(inv.event_id),
            "status": inv.status.value,
            "model_name": inv.model_name,
            "token_input": inv.token_input,
            "token_output": inv.token_output,
            "skill_call_count": inv.skill_call_count,
            "current_step": inv.current_step,
            "conclusion": None
            if inv.conclusion is None
            else {
                "verdict": inv.conclusion.verdict.value,
                "confidence": inv.conclusion.confidence,
                "risk_level": inv.conclusion.risk_level.value,
                "reasoning": inv.conclusion.reasoning,
                "recommended_action": inv.conclusion.recommended_action,
            },
            "tool_calls": [
                {
                    "step": tc.step_number,
                    "skill": tc.skill_name,
                    "success": tc.success,
                    "summary": tc.output_summary,
                }
                for tc in sorted(inv.tool_calls, key=lambda x: x.step_number)
            ],
            "message_count": len(inv.messages),
        }

    async def get_trace(self, investigation_id: UUID) -> dict | None:
        inv = await self.session.get(Investigation, investigation_id)
        if inv is None:
            return None
        await self.session.refresh(inv, ["tool_calls", "messages", "conclusion", "sop"])
        sop = inv.sop
        return {
            "investigation_id": str(inv.id),
            "event_id": str(inv.event_id),
            "closure_retry_count": inv.closure_retry_count,
            "messages": [
                {"sequence": m.sequence, "role": m.role.value, "content": m.content[:2000]}
                for m in sorted(inv.messages, key=lambda m: m.sequence)
            ],
            "tool_calls": [
                {
                    "step": tc.step_number,
                    "skill_name": tc.skill_name,
                    "input": tc.skill_input,
                    "output_summary": tc.output_summary,
                    "success": tc.success,
                }
                for tc in sorted(inv.tool_calls, key=lambda tc: tc.step_number)
            ],
            "conclusion": None
            if inv.conclusion is None
            else {
                "verdict": inv.conclusion.verdict.value,
                "reasoning": inv.conclusion.reasoning,
                "evidence_refs": inv.conclusion.evidence_refs,
                "hypotheses_evaluated": inv.conclusion.hypotheses_evaluated,
                "refutation_summary": inv.conclusion.refutation_summary,
                "evidence_closure_score": inv.conclusion.evidence_closure_score,
                "refutation_coverage": inv.conclusion.refutation_coverage,
                "closure_passed": inv.conclusion.closure_passed,
                "closure_checks": inv.conclusion.closure_checks,
            },
            "sop": None
            if sop is None
            else {
                "name": sop.name,
                "recommended_skills": sop.recommended_skills or [],
                "hypothesis_template": sop.hypothesis_template,
            },
        }

    async def _pick_events(self, limit: int) -> list[Event]:
        active_inv = select(Investigation.event_id).where(
            Investigation.status.in_([InvestigationStatus.RUNNING, InvestigationStatus.COMPLETED])
        )
        stmt = (
            select(Event)
            .where(
                Event.status == EventStatus.PENDING_REVIEW,
                Event.id.not_in(active_inv),
                Event.id.not_in(probe_event_ids_subquery()),
            )
            .order_by(Event.queue_priority.desc(), Event.risk_score.desc(), Event.last_alert_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _investigate_event(self, event: Event, config: InvestigationConfig) -> None:
        now = utc_now()
        investigation = Investigation(
            event_id=event.id,
            sop_id=None,
            status=InvestigationStatus.RUNNING,
            model_name=config.model_name,
            max_steps=config.max_steps,
            current_step=0,
            started_at=now,
        )
        self.session.add(investigation)
        await self.session.flush()

        event.status = EventStatus.INVESTIGATING
        snapshot = await build_event_entity_context_snapshot(self.session, event)
        if snapshot is not None:
            event.entity_context_snapshot = snapshot

        ctx = await build_investigation_context(
            self.session,
            investigation_id=investigation.id,
            event_id=event.id,
            model_name=config.model_name,
            alert_limit=config.alert_prompt_limit,
        )
        if ctx.sop:
            investigation.sop_id = ctx.sop.id

        loop_result = await self.agent.run(self.session, investigation, ctx, config)
        conclusion = loop_result.conclusion

        await self.session.refresh(investigation, ["tool_calls"])
        recommended_skills = list(ctx.sop.recommended_skills or []) if ctx.sop else []
        if config.supervisor_enabled:
            sup_result = InvestigationSupervisor.audit(
                conclusion,
                list(investigation.tool_calls),
                config=SupervisorConfig(
                    enabled=True,
                    block_on_fail=config.supervisor_block_on_fail,
                ),
                recommended_skills=recommended_skills,
            )
            self.session.add(
                InvestigationAudit(
                    investigation_id=investigation.id,
                    audit_type="post_complete",
                    passed=sup_result.passed,
                    findings=sup_result.to_audit_record(),
                    supervisor_model="rules",
                )
            )
            if config.supervisor_block_on_fail and not sup_result.passed:
                conclusion = degraded_conclusion("监督审计未通过，需人工复核。")
                loop_result.investigation_status = InvestigationStatus.NEEDS_HUMAN

        investigation.status = loop_result.investigation_status
        investigation.finished_at = utc_now()
        event.status = VERDICT_EVENT_STATUS.get(conclusion.verdict, EventStatus.HUMAN_PENDING)
        if event.status == EventStatus.HUMAN_PENDING:
            investigation.status = InvestigationStatus.NEEDS_HUMAN

        self._persist_conclusion(investigation.id, conclusion, loop_result.closure_result)
        await cancel_obsolete_sent_reviews_for_event(
            self.session,
            event.id,
            current_investigation_id=investigation.id,
            event_status=event.status,
        )
        if conclusion.recommended_action:
            self.session.add(
                DispositionRecord(
                    investigation_id=investigation.id,
                    suggested_action=conclusion.recommended_action,
                    status=DispositionStatus.SUGGESTED,
                )
            )

    def _persist_conclusion(
        self,
        investigation_id: UUID,
        conclusion: ConclusionPayload,
        closure_result: Any | None = None,
    ) -> None:
        closure_score = None
        refutation_cov = None
        closure_checks = None
        closure_passed = None
        if closure_result is not None:
            closure_score = closure_result.evidence_closure_score
            refutation_cov = closure_result.refutation_coverage
            closure_checks = closure_result.checks
            closure_passed = closure_result.passed

        self.session.add(
            InvestigationConclusion(
                investigation_id=investigation_id,
                verdict=conclusion.verdict,
                confidence=conclusion.confidence,
                risk_level=conclusion.risk_level,
                reasoning=conclusion.reasoning,
                recommended_action=conclusion.recommended_action,
                evidence_refs=conclusion.evidence_refs,
                human_query=conclusion.human_query,
                missing_info=conclusion.missing_info,
                suggested_assets=conclusion.suggested_assets.model_dump(),
                hypotheses_evaluated=conclusion.hypotheses_evaluated or None,
                refutation_summary=conclusion.refutation_summary,
                evidence_closure_score=closure_score,
                refutation_coverage=refutation_cov,
                closure_checks=closure_checks,
                closure_passed=closure_passed,
            )
        )
