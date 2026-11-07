"""Shared helpers for security-critical route auditing (P0-08)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.correlation import get_or_create_correlation_id
from app.api.deps import extract_client_ip
from app.services.audit import AuditPersistenceError, AuditResult, write_audit
from app.services.auth import AuthContext

logger = logging.getLogger(__name__)


def _actor_and_ip(
    request: Request, auth: AuthContext | None
) -> tuple[str | UUID | None, str | None, str]:
    correlation_id = get_or_create_correlation_id(request)
    actor_id = None
    client_ip = None
    if auth is not None:
        actor_id = auth.user_id or auth.username
        client_ip = auth.client_ip
    client_ip = client_ip or extract_client_ip(request)
    return actor_id, client_ip, correlation_id


async def security_audit(
    session: AsyncSession,
    request: Request,
    auth: AuthContext | None,
    *,
    action: str,
    resource_type: str,
    resource_id: str | UUID | None,
    detail: dict[str, Any] | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    result: AuditResult = AuditResult.SUCCESS,
    commit: bool = False,
) -> str:
    """Write a fail-closed security audit; returns correlation_id.

    Raises HTTP 503 if the audit cannot be persisted.
    """
    actor_id, client_ip, correlation_id = _actor_and_ip(request, auth)
    business_detail = {"event_level": "business", **(detail or {})}
    try:
        await write_audit(
            session,
            action=action,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=business_detail,
            before=before,
            after=after,
            result=result,
            correlation_id=correlation_id,
            client_ip=client_ip,
            commit=commit,
            fail_closed=True,
        )
    except AuditPersistenceError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Security audit unavailable; operation was not applied",
        ) from exc
    return correlation_id


async def soft_security_audit(
    session: AsyncSession,
    request: Request,
    auth: AuthContext | None,
    *,
    action: str,
    resource_type: str,
    resource_id: str | UUID | None,
    detail: dict[str, Any] | None = None,
    result: AuditResult = AuditResult.SUCCESS,
    commit: bool = True,
) -> str:
    """Best-effort security audit for ops that already committed (e.g. pipelines).

    Never silent: logs CRITICAL if the audit row cannot be written.
    """
    actor_id, client_ip, correlation_id = _actor_and_ip(request, auth)
    business_detail = {"event_level": "business", **(detail or {})}
    row = await write_audit(
        session,
        action=action,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=business_detail,
        result=result,
        correlation_id=correlation_id,
        client_ip=client_ip,
        commit=commit,
        fail_closed=False,
    )
    if row is None:
        logger.critical(
            "SECURITY AUDIT LOST action=%s resource=%s/%s correlation_id=%s",
            action,
            resource_type,
            resource_id,
            correlation_id,
        )
    return correlation_id
