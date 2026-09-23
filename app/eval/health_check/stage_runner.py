"""Run pipeline stages for a health-check probe alert."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.config import load_investigation_config
from app.agent.loop import AgentLoop
from app.agent.orchestrator import InvestigationOrchestrator
from app.aggregation.services.aggregation_service import AggregationService
from app.db.enums import HealthCheckStage
from app.eval.config import load_eval_config
from app.eval.regression.mock_llm import HealthCheckMockLLM
from app.eval.probe.guard import is_probe_alert
from app.models.ingestion import Alert
from app.models.investigation import Event, EventAlert, Investigation
from app.models.triage import TriageResult
from app.triage.services.triage_service import TriageService


async def collect_actual_state(
    session: AsyncSession,
    alert_id: UUID,
) -> dict:
    alert = await session.get(Alert, alert_id)
    if alert is None:
        return {}

    state: dict = {"alert_status": alert.status.value}
    triage = await session.execute(
        select(TriageResult).where(TriageResult.alert_id == alert_id)
    )
    triage_row = triage.scalar_one_or_none()
    if triage_row:
        state["route_decision"] = triage_row.route_decision.value

    link = await session.execute(
        select(EventAlert).where(EventAlert.alert_id == alert_id).limit(1)
    )
    event_link = link.scalar_one_or_none()
    if event_link:
        event = await session.get(Event, event_link.event_id)
        if event:
            state["event_status"] = event.status.value
            inv = await session.execute(
                select(Investigation)
                .options(selectinload(Investigation.conclusion))
                .where(Investigation.event_id == event.id)
                .order_by(Investigation.started_at.desc())
                .limit(1)
            )
            investigation = inv.scalar_one_or_none()
            if investigation:
                state["investigation_status"] = investigation.status.value
                if investigation.conclusion:
                    state["verdict"] = investigation.conclusion.verdict.value
    if is_probe_alert(alert):
        state["defense_skipped"] = True
    return state


async def run_to_stage(
    session: AsyncSession,
    alert_id: UUID,
    target_stage: HealthCheckStage,
) -> dict:
    """Advance probe alert through pipeline until target_stage is reached."""
    stage_results: dict = {}

    if target_stage == HealthCheckStage.INGESTION:
        actual = await collect_actual_state(session, alert_id)
        stage_results["ingestion"] = actual
        return stage_results

    triage_result = await TriageService(session).run(limit=50, use_lock=False)
    stage_results["triage"] = {
        "processed": triage_result.processed,
        "actual": await collect_actual_state(session, alert_id),
    }
    if target_stage == HealthCheckStage.TRIAGE:
        return stage_results

    agg_result = await AggregationService(session).run(limit=50, use_lock=False)
    stage_results["aggregation"] = {
        "processed": agg_result.processed,
        "actual": await collect_actual_state(session, alert_id),
    }
    if target_stage == HealthCheckStage.AGGREGATION:
        return stage_results

    eval_config = await load_eval_config(session)
    inv_config = replace(
        await load_investigation_config(session),
        closure_enabled=False,
        supervisor_enabled=False,
    )
    mock_llm = HealthCheckMockLLM(eval_config.health_check_agent_mock_verdict)
    orchestrator = InvestigationOrchestrator(session, agent=AgentLoop(llm=mock_llm))

    link = await session.execute(
        select(EventAlert).where(EventAlert.alert_id == alert_id).limit(1)
    )
    event_link = link.scalar_one_or_none()
    if event_link is None:
        stage_results["agent"] = {"error": "no event linked after aggregation"}
        return stage_results

    event = await session.get(Event, event_link.event_id)
    if event is None:
        stage_results["agent"] = {"error": "event not found"}
        return stage_results

    await orchestrator._investigate_event(event, inv_config)
    await session.commit()
    stage_results["agent"] = {"actual": await collect_actual_state(session, alert_id)}

    if target_stage in (HealthCheckStage.AGENT, HealthCheckStage.CONCLUSION, HealthCheckStage.FULL_CHAIN):
        actual = await collect_actual_state(session, alert_id)
        stage_results["conclusion"] = {"actual": actual}
        if target_stage == HealthCheckStage.CONCLUSION:
            return stage_results

    if target_stage == HealthCheckStage.FULL_CHAIN:
        stage_results["full_chain"] = {"actual": await collect_actual_state(session, alert_id)}
    return stage_results
