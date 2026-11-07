"""FastAPI dependencies."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.db.enums import ActorType, UserRole
from app.db.session import get_async_session
from app.services.api_key_scopes import (
    can_run_pipeline,
    is_high_risk_request,
    scoped_key_allows_request,
)
from app.services.api_keys import resolve_scoped_api_key
from app.services.audit import write_audit
from app.services.auth import (
    AuthContext,
    TOKEN_CLASS_BOOTSTRAP,
    auth_context_from_user,
    decode_access_token,
    get_user_by_id,
    is_bootstrap_path_allowed,
)
from app.services.pilot_accounts import client_ip_allowed, is_expired

logger = logging.getLogger(__name__)


def extract_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return None


async def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_async_session),
) -> AuthContext:
    """Accept scoped DB key or (if enabled) legacy env key — never plaintext in logs."""
    return await require_auth(request, authorization=None, x_api_key=x_api_key, session=session)


async def _auth_from_api_key(
    request: Request,
    *,
    x_api_key: str,
    client_ip: str | None,
    session: AsyncSession,
) -> AuthContext | None:
    # Prefer scoped DB keys (hash lookup).
    scoped = await resolve_scoped_api_key(session, x_api_key)
    if scoped is not None:
        if is_high_risk_request(request.method, request.url.path):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="High-risk operation requires JWT admin session",
            )
        scopes = list(scoped.scopes or [])
        if not scoped_key_allows_request(request.method, request.url.path, scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key scope does not allow this resource",
            )
        await session.commit()  # persist last_used_at
        ctx = AuthContext(
            user_id=scoped.user_id,
            username=f"api_key:{scoped.key_prefix}",
            is_admin=False,
            via_api_key=True,
            via_legacy_api_key=False,
            role=UserRole.OPERATOR.value,
            is_readonly=False,
            client_ip=client_ip,
            api_key_id=scoped.id,
            scopes=scopes,
        )
        request.state.auth = ctx
        return ctx

    # Legacy env API_KEY compatibility window (D-KEY-02/04).
    if (
        settings.legacy_api_key_enabled
        and settings.api_key
        and x_api_key == settings.api_key
    ):
        if is_high_risk_request(request.method, request.url.path):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="High-risk operation requires JWT admin session",
            )
        ctx = AuthContext(
            user_id=None,
            username="legacy_api_key",
            is_admin=False,  # never full admin (T-KEY-08 / O-07)
            via_api_key=True,
            via_legacy_api_key=True,
            role=UserRole.OPERATOR.value,
            is_readonly=False,
            client_ip=client_ip,
            scopes=None,
        )
        request.state.auth = ctx
        # Soft audit marker — never log the key material.
        try:
            await write_audit(
                session,
                action="auth.legacy_api_key",
                actor_id="legacy_api_key",
                resource_type="http",
                resource_id=f"{request.method} {request.url.path}",
                detail={
                    "event_level": "business",
                    "via_legacy_api_key": True,
                    "path": request.url.path,
                    "method": request.method,
                },
                commit=True,
                fail_closed=False,
            )
        except Exception:
            logger.exception("legacy api key audit failed")
        return ctx

    return None


async def require_auth(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_async_session),
) -> AuthContext:
    client_ip = extract_client_ip(request)

    if x_api_key:
        ctx = await _auth_from_api_key(
            request, x_api_key=x_api_key, client_ip=client_ip, session=session
        )
        if ctx is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key",
            )
        # High-risk routes: JWT admin only (O-07) — reject legacy/scoped early.
        if is_high_risk_request(request.method, request.url.path) and not ctx.is_jwt_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="High-risk operation requires JWT admin session",
            )
        return ctx

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            payload = decode_access_token(token)
            user_id = UUID(payload["sub"])
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            ) from exc
        user = await get_user_by_id(session, user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")

        token_tv = payload.get("tv")
        if token_tv is None or int(token_tv) != int(user.token_version or 1):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked",
            )

        if is_expired(user):
            user.is_active = False
            user.revoked_at = utc_now()
            await write_audit(
                session,
                action="auth.auto_expire",
                actor_id=user.id,
                resource_type="user",
                resource_id=user.id,
                detail={"username": user.username, "expires_at": str(user.expires_at)},
                commit=True,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Pilot account expired",
            )

        if not client_ip_allowed(client_ip, user.allowed_cidrs):
            await write_audit(
                session,
                action="auth.ip_denied",
                actor_type=ActorType.USER,
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

        is_bootstrap = payload.get("tok") == TOKEN_CLASS_BOOTSTRAP
        if is_bootstrap and not is_bootstrap_path_allowed(request.method, request.url.path):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bootstrap token cannot access this resource",
            )

        ctx = auth_context_from_user(user, client_ip=client_ip, is_bootstrap=is_bootstrap)
        request.state.auth = ctx
        return ctx

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


async def require_admin(auth: AuthContext = Depends(require_auth)) -> AuthContext:
    """JWT Admin only — legacy/scoped API keys cannot satisfy (O-07 / T-KEY-07/08)."""
    if auth.is_bootstrap:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bootstrap token cannot access this resource",
        )
    if not auth.is_jwt_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin JWT session required",
        )
    return auth


async def require_write(
    request: Request,
    auth: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_async_session),
) -> AuthContext:
    """Block pilot readonly and bootstrap from mutating / response actions."""
    if auth.is_bootstrap:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bootstrap token cannot access this resource",
        )
    if auth.is_readonly:
        await write_audit(
            session,
            action="auth.write_denied",
            actor_id=auth.user_id,
            resource_type="http",
            resource_id=f"{request.method} {request.url.path}",
            detail={"username": auth.username, "role": auth.role, "client_ip": auth.client_ip},
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pilot readonly account cannot perform this action",
        )
    if is_high_risk_request(request.method, request.url.path) and not auth.is_jwt_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="High-risk operation requires JWT admin session",
        )
    return auth


def assert_pipeline_permission(auth: AuthContext, pipeline: str) -> None:
    """Raise 403 unless caller may manually run this pipeline (O-10 / scoped)."""
    if auth.is_bootstrap or auth.is_readonly:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to run pipelines",
        )
    if auth.is_jwt_admin:
        return
    if can_run_pipeline(
        is_admin=False,
        role=auth.role,
        via_legacy_api_key=auth.via_legacy_api_key,
        scopes=auth.scopes,
        pipeline=pipeline,
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Not permitted to run pipeline '{pipeline}'",
    )
