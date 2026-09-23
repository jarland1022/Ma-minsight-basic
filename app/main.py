"""FastAPI application entrypoint (Community packaging)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    aggregation,
    alerts,
    audit_samples,
    auth,
    console,
    dashboard,
    defense_assets,
    diagnostics,
    events,
    health_checks,
    human_review,
    ingestion,
    investigations,
    license,
    playbooks,
    regression,
    system,
    triage,
)
from app.core.logging_config import configure_logging
from app.core.redis import close_redis
from app.license import get_manager, is_community_edition, read_edition
from app.scheduler.aggregation_jobs import configure_aggregation_scheduler, ensure_aggregation_scheduler_defaults
from app.scheduler.defense_asset_jobs import (
    configure_defense_asset_scheduler,
    ensure_defense_asset_scheduler_defaults,
)
from app.scheduler.human_review_jobs import (
    configure_human_review_scheduler,
    ensure_human_review_scheduler_defaults,
)
from app.scheduler.ingestion_jobs import configure_scheduler_from_db, shutdown_scheduler, start_scheduler
from app.scheduler.investigation_jobs import (
    configure_investigation_scheduler,
    ensure_investigation_scheduler_defaults,
)
from app.scheduler.eval_jobs import configure_eval_scheduler, ensure_eval_scheduler_defaults
from app.scheduler.triage_jobs import configure_triage_scheduler, ensure_triage_scheduler_defaults

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    edition = read_edition()
    pro = get_manager().allow_operation()
    logger.info("MA-MinSight starting edition=%s pro_licensed=%s", edition, pro)

    await ensure_triage_scheduler_defaults()
    await ensure_aggregation_scheduler_defaults()
    await configure_scheduler_from_db()
    await configure_triage_scheduler()
    await configure_aggregation_scheduler()

    if pro:
        await ensure_investigation_scheduler_defaults()
        await ensure_human_review_scheduler_defaults()
        await ensure_defense_asset_scheduler_defaults()
        await ensure_eval_scheduler_defaults()
        await configure_investigation_scheduler()
        await configure_human_review_scheduler()
        await configure_defense_asset_scheduler()
        await configure_eval_scheduler()
    else:
        logger.info(
            "Pro schedulers skipped (community / unlicensed): "
            "investigation, human_review, defense_assets, eval"
        )

    start_scheduler()
    yield
    shutdown_scheduler()
    await close_redis()


_edition_label = "Community" if is_community_edition() else "Professional"

app = FastAPI(
    title=f"MA-MinSight {_edition_label}",
    description=(
        "SIEM alert triage console. Community: ingest → triage → aggregate → events. "
        "Professional (license): AI Agent, WeCom review, defense assets, eval."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(events.router)
app.include_router(alerts.router)
app.include_router(console.router)
app.include_router(system.router)
app.include_router(ingestion.router)
app.include_router(diagnostics.router)
app.include_router(triage.router)
app.include_router(aggregation.router)
app.include_router(investigations.router)
app.include_router(human_review.router)
app.include_router(audit_samples.router)
app.include_router(defense_assets.router)
app.include_router(playbooks.router)
app.include_router(regression.router)
app.include_router(health_checks.router)
app.include_router(license.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "edition": read_edition()}


@app.get("/health/ready")
async def health_ready() -> dict[str, str]:
    from sqlalchemy import text

    from app.core.redis import get_redis
    from app.db.session import async_session_factory

    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        redis = await get_redis()
        await redis.ping()
    except Exception as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=f"not ready: {exc}") from exc
    return {"status": "ready", "edition": read_edition()}
