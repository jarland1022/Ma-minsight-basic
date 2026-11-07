"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    aggregation,
    alerts,
    api_keys,
    audit_logs,
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
    morning_note,
    playbooks,
    privacy,
    regression,
    system,
    triage,
    users,
)
from app.api.middleware_audit import OperationAuditMiddleware
from app.core.logging_config import configure_logging
from app.core.redis import close_redis
from app.scheduler.aggregation_jobs import configure_aggregation_scheduler, ensure_aggregation_scheduler_defaults
from app.scheduler.pilot_jobs import configure_pilot_expire_scheduler
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


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    from app.core.security_gate import assert_production_secrets_safe

    assert_production_secrets_safe()
    try:
        from app.db.session import async_session_factory
        from app.services.pilot_accounts import expire_due_pilots

        async with async_session_factory() as session:
            n = await expire_due_pilots(session)
            if n:
                await session.commit()
    except Exception:
        pass
    await ensure_triage_scheduler_defaults()
    await ensure_aggregation_scheduler_defaults()
    await ensure_investigation_scheduler_defaults()
    await ensure_human_review_scheduler_defaults()
    await ensure_defense_asset_scheduler_defaults()
    await ensure_eval_scheduler_defaults()
    await configure_scheduler_from_db()
    await configure_triage_scheduler()
    await configure_aggregation_scheduler()
    await configure_investigation_scheduler()
    await configure_human_review_scheduler()
    await configure_defense_asset_scheduler()
    await configure_eval_scheduler()
    await configure_pilot_expire_scheduler()
    start_scheduler()
    yield
    shutdown_scheduler()
    await close_redis()


app = FastAPI(
    title="MA-MinSight",
    description="Security alert triage and investigation system",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(OperationAuditMiddleware)
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
app.include_router(privacy.router)
app.include_router(ingestion.router)
app.include_router(diagnostics.router)
app.include_router(triage.router)
app.include_router(aggregation.router)
app.include_router(investigations.router)
app.include_router(human_review.router)
app.include_router(audit_samples.router)
app.include_router(defense_assets.router)
app.include_router(playbooks.router)
app.include_router(morning_note.router)
app.include_router(users.router)
app.include_router(api_keys.router)
app.include_router(audit_logs.router)
app.include_router(license.router)
app.include_router(regression.router)
app.include_router(health_checks.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


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
    return {"status": "ready"}
