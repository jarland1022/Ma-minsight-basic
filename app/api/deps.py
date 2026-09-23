"""FastAPI dependencies."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_async_session
from app.services.auth import AuthContext, decode_access_token, get_user_by_id


async def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


async def require_auth(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_async_session),
) -> AuthContext:
    if x_api_key and x_api_key == settings.api_key:
        return AuthContext(user_id=None, username="api_key", is_admin=True, via_api_key=True)

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
        return AuthContext(
            user_id=user.id,
            username=user.username,
            is_admin=user.is_admin,
            via_api_key=False,
        )

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


async def require_admin(auth: AuthContext = Depends(require_auth)) -> AuthContext:
    if not auth.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return auth


def require_pro_license() -> None:
    """Block Professional-only APIs unless a valid license is active."""
    from app.license import get_manager

    mgr = get_manager()
    if mgr.allow_operation():
        return
    st = mgr.status()
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "error": "license_required",
            "status": st.status,
            "hint": st.hint
            or "需要有效 MA-MinSight Pro License（社区版不含 AI Agent / 企微协查 / 防御资产 / 评测）",
            "license": st.to_dict(),
        },
    )
