"""Admin user / pilot account management."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.enums import UserRole
from app.db.session import get_async_session
from app.models.system import User
from app.services.audit import write_audit
from app.services.auth import AuthContext, bump_token_version
from app.services.mfa import generate_totp_secret, mfa_bundle
from app.services.pilot_accounts import (
    create_pilot_account,
    expire_due_pilots,
    revoke_user,
    user_public_dict,
)

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class CreatePilotRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    pilot_label: str | None = Field(default=None, max_length=256)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    business_days: int = Field(default=5, ge=1, le=30)
    allowed_cidrs: list[str] = Field(default_factory=list)
    email: str | None = None
    mfa_required: bool = True  # D-MFA-02: Pilot Viewer defaults to MFA required


@router.get("", dependencies=[Depends(require_admin)])
async def list_users(
    role: str | None = None,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    stmt = select(User).order_by(User.created_at.desc())
    if role:
        stmt = stmt.where(User.role == role)
    rows = list((await session.execute(stmt)).scalars().all())
    return {"items": [user_public_dict(u) for u in rows]}


@router.post("/pilots", status_code=status.HTTP_201_CREATED)
async def create_pilot(
    body: CreatePilotRequest,
    auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    try:
        user, plain, expires, enroll = await create_pilot_account(
            session,
            username=body.username,
            pilot_label=body.pilot_label,
            password=body.password,
            business_days=body.business_days,
            allowed_cidrs=body.allowed_cidrs or None,
            email=body.email,
            mfa_required=body.mfa_required,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await write_audit(
        session,
        action="user.pilot_create",
        actor_id=auth.user_id or auth.username,
        resource_type="user",
        resource_id=user.id,
        detail={
            "username": user.username,
            "expires_at": expires.isoformat(),
            "business_days": body.business_days,
            "allowed_cidrs": body.allowed_cidrs,
            "pilot_label": user.pilot_label,
            "mfa_required": body.mfa_required,
            "mfa_enrolled": bool(enroll),
        },
        commit=True,
    )
    out: dict = {
        "user": user_public_dict(user),
        "temporary_password": plain,
        "expires_at": expires.isoformat(),
        "hint": "Share username/password once with the customer. Password is not shown again.",
    }
    if enroll:
        out.update(enroll)
        out["hint"] = (
            "Share username, temporary password, and MFA QR/secret once. "
            "Customer must add the authenticator before login."
        )
    return out


@router.post("/{user_id}/mfa/reset")
async def reset_user_mfa(
    user_id: UUID,
    auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Clear MFA enrollment; next login will force setup if mfa_required stays on."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.mfa_secret = None
    bump_token_version(user)
    await write_audit(
        session,
        action="user.mfa_reset",
        actor_id=auth.user_id or auth.username,
        resource_type="user",
        resource_id=user.id,
        detail={
            "username": user.username,
            "mfa_required": bool(user.mfa_required),
            "token_version": user.token_version,
        },
        commit=True,
    )
    return {"reset": True, "user": user_public_dict(user)}


@router.post("/{user_id}/mfa/reissue")
async def reissue_user_mfa(
    user_id: UUID,
    auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Admin regenerates TOTP secret (shown once) and marks MFA required."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    secret = generate_totp_secret()
    user.mfa_secret = secret
    user.mfa_required = True
    bump_token_version(user)
    enroll = mfa_bundle(secret=secret, username=user.username)
    await write_audit(
        session,
        action="user.mfa_reissue",
        actor_id=auth.user_id or auth.username,
        resource_type="user",
        resource_id=user.id,
        detail={"username": user.username, "token_version": user.token_version},
        commit=True,
    )
    return {"user": user_public_dict(user), **enroll}


@router.post("/{user_id}/revoke")
async def revoke_account(
    user_id: UUID,
    auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    user = await revoke_user(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role == UserRole.ADMIN or user.is_admin:
        # prevent locking yourself out casually — still allow if another admin exists
        pass
    await write_audit(
        session,
        action="user.revoke",
        actor_id=auth.user_id or auth.username,
        resource_type="user",
        resource_id=user.id,
        detail={"username": user.username, "role": str(user.role)},
        commit=True,
    )
    return {"revoked": True, "user": user_public_dict(user)}


@router.post("/expire-pilots")
async def expire_pilots_now(
    auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    count = await expire_due_pilots(session)
    await write_audit(
        session,
        action="user.expire_pilots_batch",
        actor_id=auth.user_id or auth.username,
        detail={"revoked_count": count},
        commit=True,
    )
    return {"revoked_count": count}
