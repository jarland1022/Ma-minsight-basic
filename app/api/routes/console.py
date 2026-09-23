"""Console operations: pending queues and manual pipeline runs."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.aggregation.services.aggregation_service import AggregationService
from app.api.deps import require_admin, require_auth, require_pro_license
from app.console.queries import list_pending_console_items
from app.db.session import get_async_session
from app.defense_assets.pipeline import AssetPipeline
from app.eval.health_check.runner import HealthCheckRunner
from app.eval.regression.runner import RegressionRunner
from app.human_review.service import HumanReviewService
from app.ingestion.services.ingest_service import IngestService
from app.triage.services.triage_service import TriageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/console", tags=["console"])

_LICENSE_GATED_PIPELINES = frozenset(
    {"investigation", "human_review", "defense_assets", "regression", "health_check"}
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


class RunResponse(BaseModel):
    pipeline: str
    result: dict


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


@router.post("/run/{pipeline}", response_model=RunResponse, dependencies=[Depends(require_admin)])
async def manual_run_pipeline(
    pipeline: str,
    limit: int = Query(default=10, ge=1, le=500),
    source_id: UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
) -> RunResponse:
    if pipeline in _LICENSE_GATED_PIPELINES:
        require_pro_license()

    if pipeline == "triage":
        result = await TriageService(session).run(limit=limit, use_lock=True)
        payload = {
            "processed": result.processed,
            "skipped_lock": result.skipped_lock,
            "errors": result.errors,
        }
    elif pipeline == "aggregation":
        result = await AggregationService(session).run(limit=limit, use_lock=True)
        payload = {
            "processed": result.processed,
            "events_created": result.events_created,
            "events_merged": result.events_merged,
            "skipped_lock": result.skipped_lock,
            "errors": result.errors,
        }
    elif pipeline == "investigation":
        from app.agent.orchestrator import InvestigationOrchestrator

        result = await InvestigationOrchestrator(session).run(limit=limit, use_lock=True)
        payload = {
            "processed": result.processed,
            "skipped_lock": result.skipped_lock,
            "skipped_budget": result.skipped_budget,
            "errors": result.errors,
        }
    elif pipeline == "human_review":
        result = await HumanReviewService(session).run(limit=limit, use_lock=True)
        payload = {
            "dispatched": result.dispatched,
            "expired": result.expired,
            "cancelled_obsolete": result.cancelled_obsolete,
            "skipped_lock": result.skipped_lock,
            "skipped_not_configured": result.skipped_not_configured,
            "errors": result.errors,
        }
    elif pipeline == "defense_assets":
        result = await AssetPipeline(session).run(limit=limit, use_lock=True)
        payload = {
            "processed": result.processed,
            "skipped_lock": result.skipped_lock,
            "errors": result.errors,
        }
    elif pipeline == "regression":
        result = await RegressionRunner(session).run(trigger="console", use_lock=True)
        payload = {
            "run_id": str(result.run_id) if result.run_id else None,
            "total": result.total,
            "passed": result.passed,
            "failed": result.failed,
            "skipped_lock": result.skipped_lock,
            "errors": result.errors,
        }
    elif pipeline == "health_check":
        try:
            result = await HealthCheckRunner(session).run(trigger="console", use_lock=True)
            payload = {
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
    elif pipeline == "ingestion":
        try:
            if source_id is None:
                results = await IngestService(session).run_all_active()
                if not results:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="没有已启用的数据源，请先在 data_sources 中配置并启用 Wazuh 数据源",
                    )
                payload = _ingestion_payload(results)
            else:
                result = await IngestService(session).run_for_source(source_id, use_lock=True)
                payload = {
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
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown pipeline")

    return RunResponse(pipeline=pipeline, result=payload)
