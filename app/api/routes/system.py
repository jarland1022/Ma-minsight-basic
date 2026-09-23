"""System config and audit log API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_auth
from app.db.session import get_async_session
from app.models.system import AuditLog, SystemConfig
from app.services.system_config_descriptions import description_zh

router = APIRouter(prefix="/api/v1/system", tags=["system"])


class ConfigUpdateRequest(BaseModel):
    value: dict[str, Any]
    description: str | None = None


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


@router.put("/config/{key}", dependencies=[Depends(require_admin)])
async def update_config(
    key: str,
    body: ConfigUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    row = await session.get(SystemConfig, key)
    if row is None:
        row = SystemConfig(key=key, value=body.value, description=body.description)
        session.add(row)
    else:
        row.value = body.value
        if body.description:
            row.description = body.description
    await session.commit()
    return {"key": key, "value": row.value}


@router.get("/audit-logs", dependencies=[Depends(require_auth)])
async def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    action: str | None = None,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    count_stmt = select(func.count()).select_from(AuditLog)
    if action:
        count_stmt = count_stmt.where(AuditLog.action == action)
    total = int((await session.execute(count_stmt)).scalar_one() or 0)
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "action": r.action,
                "actor_type": r.actor_type.value,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "detail": r.detail,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
