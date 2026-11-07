"""Pipeline manual-run audit lifecycle: STARTED → SUCCESS|FAILED (P0-08 R2).

Pipelines commit their own work and have non-rollbackable side effects.
Therefore:
  1. Persist STARTED (fail-closed) *before* starting the pipeline.
  2. Never re-run the pipeline because a later audit update failed.
  3. If finalize fails, leave the row as STARTED and emit CRITICAL logs.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.correlation import get_or_create_correlation_id
from app.api.deps import extract_client_ip
from app.db.enums import ActorType
from app.db import session as db_session
from app.models.system import AuditLog
from app.services.audit import AuditPersistenceError, AuditResult, write_audit
from app.services.auth import AuthContext
from app.services.audit_redact import redact_for_audit

logger = logging.getLogger(__name__)

PIPELINE_MANUAL_ACTION = "pipeline.manual_run"


async def begin_pipeline_audit(
    session: AsyncSession,
    request: Request,
    auth: AuthContext,
    *,
    pipeline: str,
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    """Persist STARTED before pipeline execution. Raises 503 if write fails."""
    correlation_id = get_or_create_correlation_id(request)
    client_ip = auth.client_ip or extract_client_ip(request)
    actor_id = auth.user_id or auth.username
    payload = {
        "event_level": "business",
        "phase": "started",
        "pipeline": pipeline,
        **(detail or {}),
    }
    try:
        row = await write_audit(
            session,
            action=PIPELINE_MANUAL_ACTION,
            actor_type=ActorType.USER,
            actor_id=actor_id,
            resource_type="pipeline",
            resource_id=pipeline,
            detail=payload,
            result=AuditResult.STARTED,
            correlation_id=correlation_id,
            client_ip=client_ip,
            commit=True,
            fail_closed=True,
        )
    except AuditPersistenceError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Security audit unavailable; pipeline was not started",
        ) from exc

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Security audit unavailable; pipeline was not started",
        )
    return row


async def finalize_pipeline_audit(
    audit_id: UUID,
    *,
    success: bool,
    result_detail: dict[str, Any] | None = None,
    error: str | None = None,
) -> bool:
    """Update STARTED row to SUCCESS/FAILED using a fresh session.

    Returns True if update persisted. On failure: leaves STARTED, logs CRITICAL,
    does **not** raise (pipeline side effects already happened; no retry).
    """
    new_result = AuditResult.SUCCESS if success else AuditResult.FAILURE
    try:
        # Resolve factory at call time (tests may rebind app.db.session.async_session_factory).
        async with db_session.async_session_factory() as session:
            row = await session.get(AuditLog, audit_id)
            if row is None:
                logger.critical(
                    "PIPELINE AUDIT FINALIZE MISSING audit_id=%s intended=%s",
                    audit_id,
                    new_result.value,
                )
                return False
            if row.result != AuditResult.STARTED.value:
                # Idempotent: already finalized (duplicate finalize / concurrent).
                logger.warning(
                    "pipeline audit already finalized audit_id=%s result=%s skip→%s",
                    audit_id,
                    row.result,
                    new_result.value,
                )
                return True

            detail = dict(row.detail or {})
            detail["event_level"] = "business"
            detail["phase"] = "finished"
            if result_detail:
                detail["result_summary"] = redact_for_audit(result_detail)
            if error:
                detail["error"] = redact_for_audit(error)
            row.detail = detail
            flag_modified(row, "detail")
            row.result = new_result.value
            await session.commit()
            return True
    except Exception:
        logger.critical(
            "PIPELINE AUDIT FINALIZE FAILED audit_id=%s intended=%s "
            "(row left as started; do not re-run pipeline)",
            audit_id,
            new_result.value,
            exc_info=True,
        )
        return False
