"""Health check API."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_auth, require_pro_license
from app.db.enums import HealthCheckStage
from app.db.session import get_async_session
from app.eval.health_check.runner import HealthCheckRunner
from app.models.cache_eval import HealthCheckRun, HealthCheckScenario

router = APIRouter(
    prefix="/api/v1/health-checks",
    tags=["health-checks"],
    dependencies=[Depends(require_pro_license)],
)


class ScenarioCreateRequest(BaseModel):
    name: str
    description: str | None = None
    inject_payload: dict[str, Any]
    expected_stage: HealthCheckStage
    expected_outcome: dict[str, Any]
    is_active: bool = True


class RunResponse(BaseModel):
    total: int
    passed: int
    failed: int
    skipped_lock: bool = False
    run_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


@router.get("/scenarios", dependencies=[Depends(require_auth)])
async def list_scenarios(session: AsyncSession = Depends(get_async_session)) -> dict:
    rows = (
        await session.execute(
            select(HealthCheckScenario).order_by(HealthCheckScenario.name)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "name": r.name,
                "description": r.description,
                "expected_stage": r.expected_stage.value,
                "expected_outcome": r.expected_outcome,
                "is_active": r.is_active,
            }
            for r in rows
        ]
    }


@router.post("/scenarios", dependencies=[Depends(require_admin)], status_code=status.HTTP_201_CREATED)
async def create_scenario(
    body: ScenarioCreateRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    row = HealthCheckScenario(
        name=body.name,
        description=body.description,
        inject_payload=body.inject_payload,
        expected_stage=body.expected_stage,
        expected_outcome=body.expected_outcome,
        is_active=body.is_active,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return {"id": str(row.id), "name": row.name}


@router.post("/run", response_model=RunResponse, dependencies=[Depends(require_admin)])
async def run_health_checks(
    scenario_id: UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
) -> RunResponse:
    result = await HealthCheckRunner(session).run(scenario_id=scenario_id, trigger="api")
    return RunResponse(
        total=result.total,
        passed=result.passed,
        failed=result.failed,
        skipped_lock=result.skipped_lock,
        run_ids=[str(rid) for rid in result.run_ids],
        errors=result.errors,
    )


@router.get("/runs", dependencies=[Depends(require_auth)])
async def list_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    total = int(
        (await session.execute(select(func.count()).select_from(HealthCheckRun))).scalar_one() or 0
    )
    rows = (
        await session.execute(
            select(HealthCheckRun)
            .order_by(HealthCheckRun.run_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "scenario_id": str(r.scenario_id),
                "passed": r.passed,
                "error_message": r.error_message,
                "run_at": r.run_at.isoformat(),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/runs/latest", dependencies=[Depends(require_auth)])
async def latest_run(session: AsyncSession = Depends(get_async_session)) -> dict:
    summary = await HealthCheckRunner(session).latest_summary()
    return summary or {}

@router.get("/runs/{run_id}", dependencies=[Depends(require_auth)])
async def get_run(run_id: UUID, session: AsyncSession = Depends(get_async_session)) -> dict:
    run = await session.get(HealthCheckRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": str(run.id),
        "scenario_id": str(run.scenario_id),
        "passed": run.passed,
        "stage_results": run.stage_results,
        "error_message": run.error_message,
        "run_at": run.run_at.isoformat(),
    }
