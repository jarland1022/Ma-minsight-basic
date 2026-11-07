"""Admin audit log listing (P0-08 filters: result, correlation_id, actor)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_async_session
from app.models.system import AuditLog
from app.services.auth import AuthContext

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit-logs"])


@router.get("")
async def list_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    action_prefix: str | None = Query(None, description="Filter e.g. auth. or user."),
    action: str | None = Query(None),
    result: str | None = Query(None, description="success | failure | denied"),
    correlation_id: str | None = Query(None),
    resource_type: str | None = Query(None),
    actor_id: str | None = Query(None),
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if action_prefix:
        stmt = stmt.where(AuditLog.action.startswith(action_prefix))
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if result:
        stmt = stmt.where(AuditLog.result == result)
    if correlation_id:
        stmt = stmt.where(AuditLog.correlation_id == correlation_id)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    rows = list((await session.execute(stmt)).scalars().all())
    return {
        "items": [
            {
                "id": str(r.id),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "actor_type": r.actor_type.value if r.actor_type else None,
                "actor_id": r.actor_id,
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "detail": r.detail or {},
                "result": r.result,
                "correlation_id": r.correlation_id,
                "client_ip": r.client_ip,
            }
            for r in rows
        ]
    }
