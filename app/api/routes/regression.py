"""Regression test API."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_auth, require_pro_license
from app.db.enums import InvestigationVerdict
from app.db.session import get_async_session
from app.eval.regression.runner import RegressionRunner
from app.models.cache_eval import RegressionTestCase, RegressionTestRun

router = APIRouter(
    prefix="/api/v1/regression",
    tags=["regression"],
    dependencies=[Depends(require_pro_license)],
)


class CaseCreateRequest(BaseModel):
    name: str
    alert_payload: dict[str, Any]
    expected_verdict: InvestigationVerdict
    expected_skills: list[str] = Field(default_factory=list)
    forbidden_skills: list[str] | None = None
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True


class RunResponse(BaseModel):
    run_id: str | None
    total: int
    passed: int
    failed: int
    skipped_lock: bool = False
    errors: list[str] = Field(default_factory=list)


@router.get("/cases", dependencies=[Depends(require_auth)])
async def list_cases(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    tag: str | None = None,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    stmt = select(RegressionTestCase)
    count_stmt = select(func.count()).select_from(RegressionTestCase)
    if tag:
        stmt = stmt.where(RegressionTestCase.tags.contains([tag]))
        count_stmt = count_stmt.where(RegressionTestCase.tags.contains([tag]))
    total = int((await session.execute(count_stmt)).scalar_one() or 0)
    rows = (
        await session.execute(
            stmt.order_by(RegressionTestCase.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "name": r.name,
                "expected_verdict": r.expected_verdict.value,
                "expected_skills": r.expected_skills,
                "forbidden_skills": r.forbidden_skills,
                "tags": r.tags,
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/cases", dependencies=[Depends(require_admin)], status_code=status.HTTP_201_CREATED)
async def create_case(
    body: CaseCreateRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    row = RegressionTestCase(
        name=body.name,
        alert_payload=body.alert_payload,
        expected_verdict=body.expected_verdict,
        expected_skills=body.expected_skills,
        forbidden_skills=body.forbidden_skills,
        tags=body.tags,
        is_active=body.is_active,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return {"id": str(row.id), "name": row.name}


@router.put("/cases/{case_id}", dependencies=[Depends(require_admin)])
async def update_case(
    case_id: UUID,
    body: CaseCreateRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    row = await session.get(RegressionTestCase, case_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found")
    row.name = body.name
    row.alert_payload = body.alert_payload
    row.expected_verdict = body.expected_verdict
    row.expected_skills = body.expected_skills
    row.forbidden_skills = body.forbidden_skills
    row.tags = body.tags
    row.is_active = body.is_active
    await session.commit()
    return {"id": str(row.id), "name": row.name}


@router.post("/cases/import", dependencies=[Depends(require_admin)])
async def import_cases(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    raw = await file.read()
    imported = 0
    for line in raw.decode("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        session.add(
            RegressionTestCase(
                name=data["name"],
                alert_payload=data["alert_payload"],
                expected_verdict=InvestigationVerdict(data["expected_verdict"]),
                expected_skills=data.get("expected_skills", []),
                forbidden_skills=data.get("forbidden_skills"),
                tags=data.get("tags", []),
                is_active=data.get("is_active", True),
            )
        )
        imported += 1
    await session.commit()
    return {"imported": imported}


@router.get("/cases/export.jsonl", dependencies=[Depends(require_auth)])
async def export_cases(session: AsyncSession = Depends(get_async_session)) -> PlainTextResponse:
    rows = (await session.execute(select(RegressionTestCase).order_by(RegressionTestCase.name))).scalars().all()
    lines = []
    for row in rows:
        lines.append(
            json.dumps(
                {
                    "name": row.name,
                    "alert_payload": row.alert_payload,
                    "expected_verdict": row.expected_verdict.value,
                    "expected_skills": row.expected_skills,
                    "forbidden_skills": row.forbidden_skills,
                    "tags": row.tags,
                    "is_active": row.is_active,
                },
                ensure_ascii=False,
            )
        )
    return PlainTextResponse("\n".join(lines) + ("\n" if lines else ""), media_type="application/x-ndjson")


@router.post("/run", response_model=RunResponse, dependencies=[Depends(require_admin)])
async def run_regression(
    tag: str | None = None,
    use_real_llm: bool = Query(default=False),
    session: AsyncSession = Depends(get_async_session),
) -> RunResponse:
    result = await RegressionRunner(session).run(
        trigger="api",
        tag=tag,
        use_real_llm=use_real_llm,
        use_lock=True,
    )
    return RunResponse(
        run_id=str(result.run_id) if result.run_id else None,
        total=result.total,
        passed=result.passed,
        failed=result.failed,
        skipped_lock=result.skipped_lock,
        errors=result.errors,
    )


@router.get("/runs", dependencies=[Depends(require_auth)])
async def list_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    total = int(
        (await session.execute(select(func.count()).select_from(RegressionTestRun))).scalar_one() or 0
    )
    rows = (
        await session.execute(
            select(RegressionTestRun)
            .order_by(RegressionTestRun.run_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "trigger": r.trigger,
                "model_name": r.model_name,
                "total": r.total,
                "passed": r.passed,
                "failed": r.failed,
                "metrics": r.metrics,
                "run_at": r.run_at.isoformat(),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/runs/{run_id}", dependencies=[Depends(require_auth)])
async def get_run(run_id: UUID, session: AsyncSession = Depends(get_async_session)) -> dict:
    run = await session.get(RegressionTestRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": str(run.id),
        "trigger": run.trigger,
        "model_name": run.model_name,
        "total": run.total,
        "passed": run.passed,
        "failed": run.failed,
        "metrics": run.metrics,
        "details": run.details,
        "run_at": run.run_at.isoformat(),
    }


@router.get("/runs/compare", dependencies=[Depends(require_auth)])
async def compare_runs(
    base: UUID,
    head: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    base_run = await session.get(RegressionTestRun, base)
    head_run = await session.get(RegressionTestRun, head)
    if base_run is None or head_run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "base": {"id": str(base_run.id), "metrics": base_run.metrics, "run_at": base_run.run_at.isoformat()},
        "head": {"id": str(head_run.id), "metrics": head_run.metrics, "run_at": head_run.run_at.isoformat()},
        "delta": {
            "accuracy": (head_run.metrics or {}).get("accuracy", 0)
            - (base_run.metrics or {}).get("accuracy", 0),
            "passed_delta": head_run.passed - base_run.passed,
        },
    }
