"""Authentication helpers: JWT + password hashing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.db.enums import UserRole
from app.models.system import User

JWT_ALGORITHM = "HS256"
TOKEN_CLASS_SESSION = "session"
TOKEN_CLASS_BOOTSTRAP = "bootstrap"

# Paths allowed when JWT tok=bootstrap (method, path without trailing slash).
BOOTSTRAP_ALLOWED_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", "/api/v1/auth/me"),
        ("POST", "/api/v1/auth/change-password"),
        ("POST", "/api/v1/auth/mfa/verify"),
    }
)


@dataclass
class AuthContext:
    user_id: UUID | None
    username: str | None
    is_admin: bool
    via_api_key: bool
    role: str = UserRole.OPERATOR.value
    is_readonly: bool = False
    expires_at: datetime | None = None
    client_ip: str | None = None
    is_bootstrap: bool = False
    token_version: int | None = None
    # P0-02
    via_legacy_api_key: bool = False
    api_key_id: UUID | None = None
    scopes: list[str] | None = None

    @property
    def can_write(self) -> bool:
        return not self.is_readonly and not self.is_bootstrap

    @property
    def is_jwt_admin(self) -> bool:
        """True only for session JWT admins — not legacy/scoped API keys (O-07)."""
        return (
            bool(self.is_admin)
            and not self.via_api_key
            and not self.via_legacy_api_key
            and not self.is_bootstrap
        )


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def bump_token_version(user: User) -> int:
    user.token_version = int(user.token_version or 1) + 1
    return user.token_version


def create_access_token(
    *,
    user_id: UUID,
    username: str,
    is_admin: bool,
    role: str = UserRole.OPERATOR.value,
    expires_at: datetime | None = None,
    token_version: int = 1,
    token_class: str = TOKEN_CLASS_SESSION,
) -> str:
    now = datetime.now(UTC)
    if token_class == TOKEN_CLASS_BOOTSTRAP:
        expire = now + timedelta(minutes=settings.bootstrap_token_ttl_minutes)
    else:
        expire = now + timedelta(hours=settings.jwt_expire_hours)
    if expires_at is not None:
        exp_aware = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
        if exp_aware < expire:
            expire = exp_aware
    payload = {
        "sub": str(user_id),
        "username": username,
        "is_admin": is_admin,
        "role": role,
        "exp": expire,
        "tv": int(token_version),
        "tok": token_class,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])


def is_bootstrap_path_allowed(method: str, path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    return (method.upper(), normalized) in BOOTSTRAP_ALLOWED_ROUTES


async def authenticate_user(session: AsyncSession, username: str, password: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


def role_of(user: User) -> str:
    if isinstance(user.role, UserRole):
        return user.role.value
    if user.role:
        return str(user.role)
    return UserRole.ADMIN.value if user.is_admin else UserRole.OPERATOR.value


def auth_context_from_user(
    user: User,
    *,
    via_api_key: bool = False,
    client_ip: str | None = None,
    is_bootstrap: bool = False,
) -> AuthContext:
    role = role_of(user)
    return AuthContext(
        user_id=user.id,
        username=user.username,
        is_admin=bool(user.is_admin) or role == UserRole.ADMIN.value,
        via_api_key=via_api_key,
        role=role,
        is_readonly=role == UserRole.PILOT_READONLY.value,
        expires_at=user.expires_at,
        client_ip=client_ip,
        is_bootstrap=is_bootstrap,
        token_version=int(user.token_version or 1),
    )
