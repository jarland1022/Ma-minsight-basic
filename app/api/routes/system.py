"""System config and audit log API."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.correlation import get_or_create_correlation_id
from app.api.deps import extract_client_ip, require_admin
from app.db.session import get_async_session
from app.models.system import AuditLog, SystemConfig
from app.services.audit import AuditPersistenceError, AuditResult, write_audit
from app.services.auth import AuthContext
from app.services.system_config_descriptions import description_zh

router = APIRouter(prefix="/api/v1/system", tags=["system"])


class ConfigUpdateRequest(BaseModel):
    value: dict[str, Any]
    description: str | None = None


def _audit_row_dict(r: AuditLog) -> dict:
    return {
        "id": str(r.id),
        "action": r.action,
        "actor_type": r.actor_type.value if r.actor_type else None,
        "actor_id": r.actor_id,
        "resource_type": r.resource_type,
        "resource_id": r.resource_id,
        "detail": r.detail,
        "result": r.result,
        "correlation_id": r.correlation_id,
        "client_ip": r.client_ip,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/config", dependencies=[Depends(require_admin)])
async def list_config(session: AsyncSession = Depends(get_async_session)) -> list[dict]:
    result = await session.execute(select(SystemConfig).order_by(SystemConfig.key))
    return [
        {
            "key": row.key,
            "value": row.value,
            "description": description_zh(row.key, row.description),
        }
        for row in result.scalars().all()
    ]


@router.put("/config/{key}")
async def update_config(
    key: str,
    body: ConfigUpdateRequest,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    correlation_id = get_or_create_correlation_id(request)
    client_ip = extract_client_ip(request) or auth.client_ip
    row = await session.get(SystemConfig, key)
    before: dict[str, Any] | None
    created = False
    if row is None:
        before = None
        created = True
        row = SystemConfig(key=key, value=body.value, description=body.description)
        session.add(row)
    else:
        before = {"value": deepcopy(row.value), "description": row.description}
        row.value = body.value
        if body.description:
            row.description = body.description

    after = {"value": deepcopy(row.value), "description": row.description}
    try:
        await write_audit(
            session,
            action="config.update",
            actor_id=auth.user_id or auth.username,
            resource_type="system_config",
            resource_id=key,
            detail={"event_level": "business", "created": created, "key": key},
            before=before,
            after=after,
            result=AuditResult.SUCCESS,
            correlation_id=correlation_id,
            client_ip=client_ip,
            commit=False,
            fail_closed=True,
        )
        await session.commit()
    except AuditPersistenceError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Security audit unavailable; configuration change was not applied",
        ) from exc

    return {"key": key, "value": row.value, "correlation_id": correlation_id}


@router.get("/audit-logs", dependencies=[Depends(require_admin)])
async def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    action: str | None = None,
    action_prefix: str | None = None,
    result: str | None = Query(default=None, description="success | failure | denied"),
    correlation_id: str | None = None,
    resource_type: str | None = None,
    actor_id: str | None = None,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    stmt = select(AuditLog)
    count_stmt = select(func.count()).select_from(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if action_prefix:
        stmt = stmt.where(AuditLog.action.startswith(action_prefix))
        count_stmt = count_stmt.where(AuditLog.action.startswith(action_prefix))
    if result:
        stmt = stmt.where(AuditLog.result == result)
        count_stmt = count_stmt.where(AuditLog.result == result)
    if correlation_id:
        stmt = stmt.where(AuditLog.correlation_id == correlation_id)
        count_stmt = count_stmt.where(AuditLog.correlation_id == correlation_id)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
        count_stmt = count_stmt.where(AuditLog.resource_type == resource_type)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
        count_stmt = count_stmt.where(AuditLog.actor_id == actor_id)

    total = int((await session.execute(count_stmt)).scalar_one() or 0)
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "items": [_audit_row_dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
