"""Authentication API routes."""

from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.correlation import get_or_create_correlation_id
from app.api.deps import extract_client_ip, require_auth
from app.core.datetime_utils import utc_now
from app.core.security_gate import is_weak_password
from app.db.enums import ActorType
from app.db.session import get_async_session
from app.models.system import User
from app.services.audit import AuditPersistenceError, AuditResult, write_audit
from app.services.auth import (
    TOKEN_CLASS_BOOTSTRAP,
    TOKEN_CLASS_SESSION,
    authenticate_user,
    bump_token_version,
    create_access_token,
    hash_password,
    role_of,
    verify_password,
)
from app.services.login_rate_limit import (
    assert_login_allowed,
    clear_login_failures,
    record_login_failure,
)
from app.services.mfa import (
    create_mfa_token,
    decode_mfa_token,
    generate_totp_secret,
    mfa_bundle,
    verify_totp,
)
from app.services.pilot_accounts import client_ip_allowed, is_expired

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    user: dict | None = None
    mfa_required: bool = False
    mfa_setup_required: bool = False
    mfa_token: str | None = None
    mfa_secret: str | None = None
    otpauth_uri: str | None = None
    qr_png_data_url: str | None = None
    must_change_password: bool = False
    token_class: str | None = None
    changed: bool = False


class MfaVerifyRequest(BaseModel):
    mfa_token: str = Field(min_length=10)
    code: str = Field(min_length=6, max_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


def _user_payload(user: User) -> dict:
    role = role_of(user)
    return {
        "id": str(user.id),
        "username": user.username,
        "is_admin": bool(user.is_admin) or role == "admin",
        "role": role,
        "is_readonly": role == "pilot_readonly",
        "expires_at": user.expires_at.isoformat() if user.expires_at else None,
        "pilot_label": user.pilot_label,
        "mfa_required": bool(user.mfa_required),
        "mfa_enrolled": bool(user.mfa_secret),
        "must_change_password": bool(user.must_change_password),
    }


def _issue_access(
    user: User,
    *,
    client_ip: str | None,
    token_class: str = TOKEN_CLASS_SESSION,
) -> LoginResponse:
    role = role_of(user)
    token = create_access_token(
        user_id=user.id,
        username=user.username,
        is_admin=bool(user.is_admin) or role == "admin",
        role=role,
        expires_at=user.expires_at,
        token_version=int(user.token_version or 1),
        token_class=token_class,
    )
    if token_class == TOKEN_CLASS_SESSION:
        user.last_login_at = utc_now()
        user.last_login_ip = client_ip
    return LoginResponse(
        access_token=token,
        user=_user_payload(user),
        must_change_password=bool(user.must_change_password),
        token_class=token_class,
    )


def _mfa_setup_response(user: User) -> LoginResponse:
    pending = generate_totp_secret()
    bundle = mfa_bundle(secret=pending, username=user.username)
    mfa_token = create_mfa_token(
        user_id=user.id,
        username=user.username,
        purpose="setup",
        pending_secret=pending,
    )
    return LoginResponse(
        mfa_setup_required=True,
        mfa_token=mfa_token,
        mfa_secret=bundle["mfa_secret"],
        otpauth_uri=bundle["otpauth_uri"],
        qr_png_data_url=bundle["qr_png_data_url"],
        must_change_password=bool(user.must_change_password),
    )


async def _guard_login_user(user: User, *, client_ip: str | None, session: AsyncSession) -> None:
    if is_expired(user):
        user.is_active = False
        user.revoked_at = utc_now()
        await write_audit(
            session,
            action="auth.login_expired",
            actor_id=user.id,
            resource_type="user",
            resource_id=user.id,
            detail={"username": user.username, "expires_at": str(user.expires_at)},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Pilot account expired")

    if not client_ip_allowed(client_ip, user.allowed_cidrs):
        await write_audit(
            session,
            action="auth.login_ip_denied",
            actor_id=user.id,
            resource_type="user",
            resource_id=user.id,
            detail={"username": user.username, "client_ip": client_ip},
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client IP not allowed for this account",
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> LoginResponse:
    client_ip = extract_client_ip(request)
    await assert_login_allowed(client_ip, body.username)

    user = await authenticate_user(session, body.username, body.password)
    if user is None:
        await record_login_failure(client_ip, body.username)
        await write_audit(
            session,
            action="auth.login_failed",
            actor_type=ActorType.USER,
            actor_id=body.username,
            detail={"username": body.username, "client_ip": client_ip},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    await clear_login_failures(client_ip, body.username)
    await _guard_login_user(user, client_ip=client_ip, session=session)

    # Weak password at login forces change without resetting the hash (D-AUTH-07).
    if is_weak_password(body.password):
        user.must_change_password = True

    if user.must_change_password:
        resp = _issue_access(user, client_ip=client_ip, token_class=TOKEN_CLASS_BOOTSTRAP)
        await write_audit(
            session,
            action="auth.login_bootstrap",
            actor_id=user.id,
            resource_type="user",
            resource_id=user.id,
            detail={
                "username": user.username,
                "role": role_of(user),
                "client_ip": client_ip,
                "reason": "must_change_password",
            },
            commit=True,
        )
        return resp

    if user.mfa_required:
        if user.mfa_secret:
            mfa_token = create_mfa_token(
                user_id=user.id,
                username=user.username,
                purpose="verify",
            )
            await write_audit(
                session,
                action="auth.mfa_challenge",
                actor_id=user.id,
                resource_type="user",
                resource_id=user.id,
                detail={"username": user.username, "client_ip": client_ip, "purpose": "verify"},
                commit=True,
            )
            return LoginResponse(mfa_required=True, mfa_token=mfa_token)

        resp = _mfa_setup_response(user)
        await write_audit(
            session,
            action="auth.mfa_setup_challenge",
            actor_id=user.id,
            resource_type="user",
            resource_id=user.id,
            detail={"username": user.username, "client_ip": client_ip},
            commit=True,
        )
        return resp

    resp = _issue_access(user, client_ip=client_ip, token_class=TOKEN_CLASS_SESSION)
    await write_audit(
        session,
        action="auth.login",
        actor_id=user.id,
        resource_type="user",
        resource_id=user.id,
        detail={
            "username": user.username,
            "role": role_of(user),
            "client_ip": client_ip,
            "pilot_label": user.pilot_label,
            "mfa": False,
        },
        commit=True,
    )
    return resp


@router.post("/mfa/verify", response_model=LoginResponse)
async def mfa_verify(
    body: MfaVerifyRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> LoginResponse:
    client_ip = extract_client_ip(request)
    try:
        payload = decode_mfa_token(body.mfa_token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired MFA token")

    purpose = payload.get("purpose")
    user_id = UUID(str(payload["sub"]))
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    await _guard_login_user(user, client_ip=client_ip, session=session)

    if purpose == "verify":
        if not user.mfa_secret or not verify_totp(user.mfa_secret, body.code):
            await write_audit(
                session,
                action="auth.mfa_failed",
                actor_id=user.id,
                resource_type="user",
                resource_id=user.id,
                detail={"username": user.username, "client_ip": client_ip, "purpose": "verify"},
                commit=True,
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")
    elif purpose == "setup":
        pending = payload.get("pending_secret")
        if not pending or not verify_totp(pending, body.code):
            await write_audit(
                session,
                action="auth.mfa_failed",
                actor_id=user.id,
                resource_type="user",
                resource_id=user.id,
                detail={"username": user.username, "client_ip": client_ip, "purpose": "setup"},
                commit=True,
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")
        user.mfa_secret = pending
        user.mfa_required = True
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown MFA purpose")

    if user.must_change_password:
        resp = _issue_access(user, client_ip=client_ip, token_class=TOKEN_CLASS_BOOTSTRAP)
    else:
        resp = _issue_access(user, client_ip=client_ip, token_class=TOKEN_CLASS_SESSION)

    await write_audit(
        session,
        action="auth.login",
        actor_id=user.id,
        resource_type="user",
        resource_id=user.id,
        detail={
            "username": user.username,
            "role": role_of(user),
            "client_ip": client_ip,
            "pilot_label": user.pilot_label,
            "mfa": True,
            "mfa_purpose": purpose,
            "token_class": resp.token_class,
        },
        commit=True,
    )
    return resp


@router.get("/me")
async def me(
    auth=Depends(require_auth),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    out: dict = {
        "user_id": str(auth.user_id) if auth.user_id else None,
        "username": auth.username,
        "is_admin": auth.is_admin,
        "via_api_key": auth.via_api_key,
        "role": auth.role,
        "is_readonly": auth.is_readonly,
        "expires_at": auth.expires_at.isoformat() if auth.expires_at else None,
        "client_ip": auth.client_ip,
        "token_class": TOKEN_CLASS_BOOTSTRAP if auth.is_bootstrap else TOKEN_CLASS_SESSION,
        "is_bootstrap": bool(auth.is_bootstrap),
    }
    if auth.user_id and not auth.via_api_key:
        user = await session.get(User, auth.user_id)
        if user is not None:
            out["must_change_password"] = bool(user.must_change_password)
            out["mfa_required"] = bool(user.mfa_required)
            out["mfa_enrolled"] = bool(user.mfa_secret)
    return out


@router.post("/change-password", response_model=LoginResponse)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    auth=Depends(require_auth),
    session: AsyncSession = Depends(get_async_session),
) -> LoginResponse:
    if auth.via_api_key or auth.user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not available for API key")
    if is_weak_password(body.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password is too weak",
        )
    user = await session.get(User, auth.user_id)
    if user is None or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid current password")

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    bump_token_version(user)

    client_ip = extract_client_ip(request)
    correlation_id = get_or_create_correlation_id(request)
    try:
        await write_audit(
            session,
            action="auth.change_password",
            actor_id=user.id,
            resource_type="user",
            resource_id=user.id,
            detail={"username": user.username, "token_version": user.token_version},
            result=AuditResult.SUCCESS,
            correlation_id=correlation_id,
            client_ip=client_ip,
            commit=True,
            fail_closed=True,
        )
    except AuditPersistenceError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Security audit unavailable; password change was not applied",
        ) from exc

    # Continue enrollment: MFA setup challenge or full/bootstrap session.
    if user.mfa_required and not user.mfa_secret:
        resp = _mfa_setup_response(user)
        resp.changed = True
        return resp

    token_class = TOKEN_CLASS_BOOTSTRAP if user.must_change_password else TOKEN_CLASS_SESSION
    resp = _issue_access(user, client_ip=client_ip, token_class=token_class)
    resp.changed = True
    return resp


@router.post("/logout")
async def logout(
    request: Request,
    auth=Depends(require_auth),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Record logout; client discards the JWT locally (stateless)."""
    correlation_id = get_or_create_correlation_id(request)
    client_ip = extract_client_ip(request) or auth.client_ip
    await write_audit(
        session,
        action="auth.logout",
        actor_id=auth.user_id or auth.username,
        resource_type="user",
        resource_id=auth.user_id,
        detail={"username": auth.username, "token_class": "bootstrap" if auth.is_bootstrap else "session"},
        result=AuditResult.SUCCESS,
        correlation_id=correlation_id,
        client_ip=client_ip,
        commit=True,
        fail_closed=False,
    )
    return {"logged_out": True, "correlation_id": correlation_id}
