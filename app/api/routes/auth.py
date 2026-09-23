"""Authentication API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_auth
from app.db.session import get_async_session
from app.services.auth import authenticate_user, create_access_token, hash_password, verify_password
from app.models.system import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_async_session)) -> LoginResponse:
    user = await authenticate_user(session, body.username, body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user_id=user.id, username=user.username, is_admin=user.is_admin)
    return LoginResponse(
        access_token=token,
        user={"id": str(user.id), "username": user.username, "is_admin": user.is_admin},
    )


@router.get("/me")
async def me(auth=Depends(require_auth)) -> dict:
    return {
        "user_id": str(auth.user_id) if auth.user_id else None,
        "username": auth.username,
        "is_admin": auth.is_admin,
        "via_api_key": auth.via_api_key,
    }


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    auth=Depends(require_auth),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    if auth.via_api_key or auth.user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not available for API key")
    user = await session.get(User, auth.user_id)
    if user is None or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid current password")
    user.password_hash = hash_password(body.new_password)
    await session.commit()
    return {"changed": True}
