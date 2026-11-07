"""Write immutable audit log rows (P0-08 security audit)."""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import ActorType
from app.models.system import AuditLog
from app.services.audit_redact import redact_for_audit

logger = logging.getLogger(__name__)


class AuditResult(StrEnum):
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


class AuditPersistenceError(RuntimeError):
    """Raised when a fail-closed security audit cannot be persisted."""


# Fail-closed business mutations: audit row must persist in the same transaction
# as the change (or operation is aborted with 503).
HIGH_RISK_AUDIT_ACTIONS: frozenset[str] = frozenset(
    {
        "config.update",
        "disposition.confirm",
        "disposition.reject",
        "disposition.simulation.approve",
        "disposition.simulation.reject",
        "whitelist.candidate.confirm",
        "whitelist.candidate.reject",
        "profile.suggestion.apply",
        "profile.suggestion.reject",
        "rule.candidate.review",
        "data.export",
        "data.import",
        "user.pilot_create",
        "user.mfa_reset",
        "user.mfa_reissue",
        "user.revoke",
        "auth.change_password",
        "license.import",
        "regression.case.update",
        "regression.case.create",
        "regression.case.import",
        "api_key.create",
        "api_key.revoke",
        "api_key.rotate",
    }
)

# Soft-fail + loud ERROR/CRITICAL (never silent). Login/logout stay available if
# audit DB blips. pipeline.manual_run STARTED is fail-closed via
# begin_pipeline_audit(fail_closed=True); finalize is soft (row may stay started).
SOFT_SECURITY_AUDIT_ACTIONS: frozenset[str] = frozenset(
    {
        "pipeline.manual_run",
        "auth.login",
        "auth.login_failed",
        "auth.login_bootstrap",
        "auth.logout",
        "auth.mfa_challenge",
        "auth.mfa_setup_challenge",
        "auth.mfa_failed",
    }
)


def is_high_risk_action(action: str) -> bool:
    return action in HIGH_RISK_AUDIT_ACTIONS or action.startswith("config.")


async def write_audit(
    session: AsyncSession,
    *,
    action: str,
    actor_type: ActorType = ActorType.USER,
    actor_id: str | UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | UUID | None = None,
    detail: dict[str, Any] | None = None,
    result: AuditResult | str | None = None,
    correlation_id: str | None = None,
    client_ip: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    commit: bool = False,
    fail_closed: bool | None = None,
) -> AuditLog | None:
    """Persist an audit row with secret redaction.

    fail_closed:
      - True  → raise AuditPersistenceError on write failure (high-risk default)
      - False → log ERROR and return None (middleware / low-risk)
      - None  → auto from HIGH_RISK_AUDIT_ACTIONS
    """
    if fail_closed is None:
        fail_closed = is_high_risk_action(action)

    safe_detail: dict[str, Any] = dict(redact_for_audit(detail or {}) or {})
    if before is not None:
        safe_detail["before"] = redact_for_audit(before)
    if after is not None:
        safe_detail["after"] = redact_for_audit(after)

    result_value: str | None
    if result is None:
        result_value = None
    elif isinstance(result, AuditResult):
        result_value = result.value
    else:
        result_value = str(result)

    row = AuditLog(
        actor_type=actor_type,
        actor_id=str(actor_id) if actor_id is not None else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        detail=safe_detail,
        result=result_value,
        correlation_id=correlation_id,
        client_ip=client_ip,
    )

    try:
        session.add(row)
        if commit:
            await session.commit()
        else:
            await session.flush()
        return row
    except Exception as exc:
        logger.error(
            "audit write failed action=%s fail_closed=%s correlation_id=%s",
            action,
            fail_closed,
            correlation_id,
            exc_info=True,
        )
        if fail_closed:
            raise AuditPersistenceError(
                f"Security audit write failed for action={action}"
            ) from exc
        return None
