"""Defense asset API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_auth, require_pro_license
from app.services.auth import AuthContext
from app.db.enums import CandidateStatus, DispositionSimulationApprovalStatus
from app.db.session import get_async_session
from app.defense_assets.disposition.service import DispositionService
from app.defense_assets.disposition.simulation_service import DispositionSimulationService
from app.defense_assets.pipeline import AssetPipeline
from app.defense_assets.profile.applier import ProfileUpdateApplier
from app.defense_assets.whitelist.promoter import WhitelistPromoter
from app.defense_assets.config import load_defense_asset_config
from app.models.defense_assets import DispositionRecord, DispositionSimulation, JudgmentCase, RuleCandidate
from app.models.triage import WhitelistRule

router = APIRouter(tags=["defense-assets"], dependencies=[Depends(require_pro_license)])


class PipelineRunResponse(BaseModel):
    processed: int
    skipped_lock: bool
    skipped_disabled: bool
    errors: list[str]


class DispositionConfirmRequest(BaseModel):
    confirmed_action: str | None = None


class RuleReviewRequest(BaseModel):
    status: CandidateStatus


@router.post(
    "/api/v1/defense-assets/run",
    response_model=PipelineRunResponse,
    dependencies=[Depends(require_auth)],
)
async def run_defense_assets(
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
) -> PipelineRunResponse:
    pipeline = AssetPipeline(session)
    result = await pipeline.run(limit=limit, use_lock=True)
    return PipelineRunResponse(
        processed=result.processed,
        skipped_lock=result.skipped_lock,
        skipped_disabled=result.skipped_disabled,
        errors=result.errors,
    )


@router.get("/api/v1/defense-assets/stats", dependencies=[Depends(require_auth)])
async def defense_asset_stats(session: AsyncSession = Depends(get_async_session)) -> dict:
    pipeline = AssetPipeline(session)
    return await pipeline.stats()


@router.get("/api/v1/judgment-cases", dependencies=[Depends(require_auth)])
async def list_judgment_cases(
    category: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict]:
    stmt = select(JudgmentCase).where(JudgmentCase.is_active.is_(True)).limit(limit)
    if category:
        stmt = stmt.where(JudgmentCase.alert_category == category)
    result = await session.execute(stmt)
    return [
        {
            "id": str(c.id),
            "alert_category": c.alert_category,
            "feature_summary": c.feature_summary,
            "verdict": c.verdict.value,
            "usage_count": c.usage_count,
        }
        for c in result.scalars().all()
    ]


@router.get("/api/v1/judgment-cases/{case_id}", dependencies=[Depends(require_auth)])
async def get_judgment_case(
    case_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    case = await session.get(JudgmentCase, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return {
        "id": str(case.id),
        "investigation_id": str(case.investigation_id),
        "feature_summary": case.feature_summary,
        "alert_category": case.alert_category,
        "entity_tags": case.entity_tags,
        "investigation_trace": case.investigation_trace,
        "verdict": case.verdict.value,
        "reasoning": case.reasoning,
        "human_feedback": case.human_feedback,
    }


@router.post("/api/v1/whitelist-candidates/{candidate_id}/confirm", dependencies=[Depends(require_auth)])
async def confirm_whitelist_candidate(
    candidate_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    config = await load_defense_asset_config(session)
    promoter = WhitelistPromoter(session, config)
    rule = await promoter.confirm_candidate(candidate_id)
    await session.commit()
    return {
        "promoted": rule is not None,
        "rule_id": str(rule.id) if rule else None,
    }


@router.post("/api/v1/whitelist-candidates/{candidate_id}/reject", dependencies=[Depends(require_auth)])
async def reject_whitelist_candidate(
    candidate_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    config = await load_defense_asset_config(session)
    promoter = WhitelistPromoter(session, config)
    ok = await promoter.reject_candidate(candidate_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    await session.commit()
    return {"rejected": True}


@router.post("/api/v1/profile-suggestions/{suggestion_id}/apply", dependencies=[Depends(require_auth)])
async def apply_profile_suggestion(
    suggestion_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    applier = ProfileUpdateApplier(session)
    memory = await applier.apply(suggestion_id)
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")
    await session.commit()
    return {"applied": True, "memory_id": str(memory.id)}


@router.post("/api/v1/profile-suggestions/{suggestion_id}/reject", dependencies=[Depends(require_auth)])
async def reject_profile_suggestion(
    suggestion_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    applier = ProfileUpdateApplier(session)
    ok = await applier.reject(suggestion_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")
    await session.commit()
    return {"rejected": True}


@router.get("/api/v1/rule-candidates", dependencies=[Depends(require_auth)])
async def list_rule_candidates(
    session: AsyncSession = Depends(get_async_session),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    result = await session.execute(select(RuleCandidate).limit(limit))
    return [
        {
            "id": str(r.id),
            "investigation_id": str(r.investigation_id),
            "status": r.status.value,
            "reason": r.reason,
        }
        for r in result.scalars().all()
    ]


@router.post("/api/v1/rule-candidates/{candidate_id}/review", dependencies=[Depends(require_auth)])
async def review_rule_candidate(
    candidate_id: UUID,
    body: RuleReviewRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    candidate = await session.get(RuleCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    if body.status not in (CandidateStatus.ACCEPTED, CandidateStatus.REJECTED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
    candidate.status = body.status
    await session.commit()
    return {"status": candidate.status.value}


@router.post("/api/v1/disposition/{record_id}/confirm", dependencies=[Depends(require_auth)])
async def confirm_disposition(
    record_id: UUID,
    body: DispositionConfirmRequest,
    auth: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    service = DispositionService(session)
    record = await service.confirm(
        record_id,
        confirmed_action=body.confirmed_action,
        confirmed_by_id=auth.user_id,
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    await session.commit()
    return {"status": record.status.value}


@router.post("/api/v1/disposition/{record_id}/reject", dependencies=[Depends(require_auth)])
async def reject_disposition(
    record_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    service = DispositionService(session)
    ok = await service.reject(record_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    await session.commit()
    return {"status": "rejected"}


@router.get("/api/v1/disposition-simulations", dependencies=[Depends(require_auth)])
async def list_disposition_simulations(
    status: DispositionSimulationApprovalStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict]:
    stmt = select(DispositionSimulation).order_by(DispositionSimulation.created_at.desc()).limit(limit)
    if status is not None:
        stmt = stmt.where(DispositionSimulation.approval_status == status)
    result = await session.execute(stmt)
    return [_simulation_row(s) for s in result.scalars().all()]


@router.post(
    "/api/v1/disposition-simulations/{simulation_id}/approve",
    dependencies=[Depends(require_auth)],
)
async def approve_disposition_simulation(
    simulation_id: UUID,
    auth: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    service = DispositionSimulationService(session)
    record = await service.approve(simulation_id, approved_by_id=auth.user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    await session.commit()
    return {"approval_status": record.approval_status.value}


@router.post(
    "/api/v1/disposition-simulations/{simulation_id}/reject",
    dependencies=[Depends(require_auth)],
)
async def reject_disposition_simulation(
    simulation_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    service = DispositionSimulationService(session)
    ok = await service.reject(simulation_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    await session.commit()
    return {"approval_status": "rejected"}


def _simulation_row(record: DispositionSimulation) -> dict:
    impact = record.simulated_impact or {}
    return {
        "id": str(record.id),
        "investigation_id": str(record.investigation_id),
        "action_type": record.action_type,
        "action_params": record.action_params,
        "simulated_impact": impact,
        "approval_status": record.approval_status.value,
        "created_at": record.created_at.isoformat(),
        "affected_host_count": impact.get("affected_host_count"),
        "estimated_downtime_minutes": impact.get("estimated_downtime_minutes"),
    }


@router.get("/api/v1/whitelist-rules", dependencies=[Depends(require_auth)])
async def list_whitelist_rules(session: AsyncSession = Depends(get_async_session)) -> list[dict]:
    from app.db.enums import WhitelistRuleStatus

    result = await session.execute(
        select(WhitelistRule).where(WhitelistRule.status == WhitelistRuleStatus.ACTIVE)
    )
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "rule_type": r.rule_type.value,
            "match_pattern": r.match_pattern,
            "effective_from": r.effective_from.isoformat(),
            "effective_until": r.effective_until.isoformat(),
        }
        for r in result.scalars().all()
    ]
