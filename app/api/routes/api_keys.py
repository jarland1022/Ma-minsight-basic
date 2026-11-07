"""Scoped API key admin CRUD (P0-02 / T-KEY-01..09)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.audit_helpers import security_audit
from app.api.deps import require_admin
from app.db.session import get_async_session
from app.services.api_keys import (
    api_key_public_dict,
    create_api_key,
    list_api_keys,
    revoke_api_key,
    rotate_api_key,
)
from app.services.audit import AuditResult
from app.services.auth import AuthContext

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    scopes: list[str] = Field(min_length=1)
    expires_at: datetime | None = None


class RotateApiKeyRequest(BaseModel):
    scopes: list[str] | None = None
    expires_at: datetime | None = None


@router.get("")
async def list_keys(
    auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    rows = await list_api_keys(session)
    return {"items": [api_key_public_dict(r) for r in rows]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_key(
    body: CreateApiKeyRequest,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    if auth.user_id is None:
        raise HTTPException(status_code=400, detail="JWT admin user required to own API keys")
    try:
        row, plaintext = await create_api_key(
            session,
            user_id=auth.user_id,
            name=body.name,
            scopes=body.scopes,
            expires_at=body.expires_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await security_audit(
        session,
        request,
        auth,
        action="api_key.create",
        resource_type="api_key",
        resource_id=row.id,
        detail={
            "name": row.name,
            "key_prefix": row.key_prefix,
            "scopes": row.scopes,
            # never include plaintext
        },
        result=AuditResult.SUCCESS,
        commit=False,
    )
    await session.commit()
    return {
        "key": api_key_public_dict(row),
        "api_key": plaintext,  # once only (T-KEY-02)
        "hint": "Store this secret now; it will not be shown again.",
    }


@router.post("/{key_id}/revoke")
async def revoke_key(
    key_id: UUID,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    row = await revoke_api_key(session, key_id)
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found")
    await security_audit(
        session,
        request,
        auth,
        action="api_key.revoke",
        resource_type="api_key",
        resource_id=key_id,
        detail={"key_prefix": row.key_prefix},
        result=AuditResult.SUCCESS,
        commit=False,
    )
    await session.commit()
    return {"revoked": True, "key": api_key_public_dict(row)}


@router.post("/{key_id}/rotate")
async def rotate_key(
    key_id: UUID,
    body: RotateApiKeyRequest,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    try:
        result = await rotate_api_key(
            session,
            key_id=key_id,
            scopes=body.scopes,
            expires_at=body.expires_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="API key not found")
    new_row, plaintext = result
    await security_audit(
        session,
        request,
        auth,
        action="api_key.rotate",
        resource_type="api_key",
        resource_id=new_row.id,
        detail={
            "key_prefix": new_row.key_prefix,
            "rotated_from_id": str(key_id),
            "scopes": new_row.scopes,
        },
        result=AuditResult.SUCCESS,
        commit=False,
    )
    await session.commit()
    return {
        "key": api_key_public_dict(new_row),
        "api_key": plaintext,
        "hint": "Store this secret now; old key is revoked immediately.",
    }
