"""Console operations: pending queues and manual pipeline runs."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.orchestrator import InvestigationOrchestrator
from app.aggregation.services.aggregation_service import AggregationService
from app.api.deps import assert_pipeline_permission, require_auth
from app.console.queries import list_pending_console_items
from app.db.session import get_async_session
from app.defense_assets.pipeline import AssetPipeline
from app.eval.health_check.runner import HealthCheckRunner
from app.eval.regression.runner import RegressionRunner
from app.human_review.service import HumanReviewService
from app.ingestion.services.ingest_service import IngestService
from app.services.auth import AuthContext
from app.services.pipeline_audit import begin_pipeline_audit, finalize_pipeline_audit
from app.triage.services.triage_service import TriageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/console", tags=["console"])

_KNOWN_PIPELINES = frozenset(
    {
        "triage",
        "aggregation",
        "investigation",
        "human_review",
        "defense_assets",
        "regression",
        "health_check",
        "ingestion",
    }
)


def _ingestion_payload(results: list) -> dict:
    errors = [err for r in results for err in r.errors]
    return {
        "sources": len(results),
        "inserted": sum(r.total_inserted for r in results),
        "duplicates": sum(r.total_duplicates for r in results),
        "fetched": sum(sum(b.fetched for b in r.batches) for r in results),
        "skipped_lock": sum(1 for r in results if r.skipped_lock),
        "skipped_no_adapter": sum(1 for r in results if r.skipped_no_adapter),
        "errors": errors,
    }


def _summary(payload: dict) -> dict:
    return {
        k: payload.get(k)
        for k in (
            "processed",
            "inserted",
            "events_created",
            "dispatched",
            "total",
            "passed",
            "failed",
            "skipped_lock",
            "errors",
        )
        if k in payload
    }


class RunResponse(BaseModel):
    pipeline: str
    result: dict
    audit_id: str | None = None
    correlation_id: str | None = None
    audit_finalized: bool = True


@router.get("/pending", dependencies=[Depends(require_auth)])
async def pending_items(session: AsyncSession = Depends(get_async_session)) -> dict:
    return await list_pending_console_items(session)


@router.get("/investigation-sops", dependencies=[Depends(require_auth)])
async def list_investigation_sops(
    category: str | None = None,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    from sqlalchemy import select

    from app.models.investigation import InvestigationSop

    stmt = select(InvestigationSop).where(InvestigationSop.is_active.is_(True))
    if category:
        stmt = stmt.where(InvestigationSop.alert_category == category)
    stmt = stmt.order_by(InvestigationSop.alert_category, InvestigationSop.version.desc())
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "items": [
            {
                "id": str(s.id),
                "alert_category": s.alert_category,
                "name": s.name,
                "recommended_skills": s.recommended_skills or [],
                "hypothesis_template": s.hypothesis_template,
                "termination_policy": s.termination_policy,
                "version": s.version,
            }
            for s in rows
        ]
    }


async def _execute_pipeline(
    session: AsyncSession,
    pipeline: str,
    *,
    limit: int,
    source_id: UUID | None,
) -> dict:
    if pipeline == "triage":
        result = await TriageService(session).run(limit=limit, use_lock=True)
        return {
            "processed": result.processed,
            "skipped_lock": result.skipped_lock,
            "errors": result.errors,
        }
    if pipeline == "aggregation":
        result = await AggregationService(session).run(limit=limit, use_lock=True)
        return {
            "processed": result.processed,
            "events_created": result.events_created,
            "events_merged": result.events_merged,
            "skipped_lock": result.skipped_lock,
            "errors": result.errors,
        }
    if pipeline == "investigation":
        result = await InvestigationOrchestrator(session).run(limit=limit, use_lock=True)
        return {
            "processed": result.processed,
            "skipped_lock": result.skipped_lock,
            "skipped_budget": result.skipped_budget,
            "errors": result.errors,
        }
    if pipeline == "human_review":
        result = await HumanReviewService(session).run(limit=limit, use_lock=True)
        return {
            "dispatched": result.dispatched,
            "expired": result.expired,
            "cancelled_obsolete": result.cancelled_obsolete,
            "skipped_lock": result.skipped_lock,
            "skipped_not_configured": result.skipped_not_configured,
            "errors": result.errors,
        }
    if pipeline == "defense_assets":
        result = await AssetPipeline(session).run(limit=limit, use_lock=True)
        return {
            "processed": result.processed,
            "skipped_lock": result.skipped_lock,
            "errors": result.errors,
        }
    if pipeline == "regression":
        result = await RegressionRunner(session).run(trigger="console", use_lock=True)
        return {
            "run_id": str(result.run_id) if result.run_id else None,
            "total": result.total,
            "passed": result.passed,
            "failed": result.failed,
            "skipped_lock": result.skipped_lock,
            "errors": result.errors,
        }
    if pipeline == "health_check":
        try:
            result = await HealthCheckRunner(session).run(trigger="console", use_lock=True)
            return {
                "total": result.total,
                "passed": result.passed,
                "failed": result.failed,
                "skipped_lock": result.skipped_lock,
                "errors": result.errors,
            }
        except Exception as exc:
            logger.exception("Manual health_check failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"链路探针失败：{exc}",
            ) from exc
    if pipeline == "ingestion":
        try:
            if source_id is None:
                results = await IngestService(session).run_all_active()
                if not results:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="没有已启用的数据源，请先在 data_sources 中配置并启用 Wazuh 数据源",
                    )
                return _ingestion_payload(results)
            result = await IngestService(session).run_for_source(source_id, use_lock=True)
            return {
                "inserted": result.total_inserted,
                "duplicates": result.total_duplicates,
                "fetched": sum(b.fetched for b in result.batches),
                "skipped_lock": result.skipped_lock,
                "errors": list(result.errors),
            }
        except HTTPException:
            raise
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Manual ingestion failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"告警入库失败：{exc}",
            ) from exc
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown pipeline")


@router.post("/run/{pipeline}", response_model=RunResponse)
async def manual_run_pipeline(
    pipeline: str,
    request: Request,
    limit: int = Query(default=10, ge=1, le=500),
    source_id: UUID | None = None,
    auth: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_async_session),
) -> RunResponse:
    if pipeline not in _KNOWN_PIPELINES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown pipeline")
    assert_pipeline_permission(auth, pipeline)

    # Fail-closed STARTED before any pipeline side effects.
    started = await begin_pipeline_audit(
        session,
        request,
        auth,
        pipeline=pipeline,
        detail={"limit": limit, "source_id": str(source_id) if source_id else None},
    )
    correlation_id = started.correlation_id

    try:
        payload = await _execute_pipeline(session, pipeline, limit=limit, source_id=source_id)
    except HTTPException as exc:
        # Do not re-run pipeline; finalize FAILED then propagate.
        await finalize_pipeline_audit(
            started.id,
            success=False,
            error=str(exc.detail),
        )
        raise
    except Exception as exc:
        await finalize_pipeline_audit(
            started.id,
            success=False,
            error=str(exc),
        )
        raise

    finalized = await finalize_pipeline_audit(
        started.id,
        success=True,
        result_detail=_summary(payload),
    )
    return RunResponse(
        pipeline=pipeline,
        result=payload,
        audit_id=str(started.id),
        correlation_id=correlation_id,
        audit_finalized=finalized,
    )
