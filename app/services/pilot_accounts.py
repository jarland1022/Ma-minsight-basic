"""Create / revoke time-boxed pilot readonly accounts."""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta
from ipaddress import ip_address, ip_network
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now
from app.db.enums import UserRole
from app.models.system import User
from app.services.auth import bump_token_version, hash_password
from app.services.mfa import generate_totp_secret, mfa_bundle


def add_business_days(start: datetime, days: int = 5) -> datetime:
    """Add N weekdays (Mon–Fri); ignores public holidays."""
    cur = start
    added = 0
    while added < days:
        cur = cur + timedelta(days=1)
        if cur.weekday() < 5:
            added += 1
    return cur


def generate_temp_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def client_ip_allowed(client_ip: str | None, allowed_cidrs: list[Any] | None) -> bool:
    if not allowed_cidrs:
        return True
    if not client_ip:
        return False
    try:
        addr = ip_address(client_ip.split("%")[0])
    except ValueError:
        return False
    for raw in allowed_cidrs:
        try:
            net = ip_network(str(raw), strict=False)
        except ValueError:
            continue
        if addr in net:
            return True
    return False


def is_expired(user: User, *, now: datetime | None = None) -> bool:
    if user.expires_at is None:
        return False
    ts = now or utc_now()
    exp = user.expires_at
    if exp.tzinfo is not None:
        exp = exp.replace(tzinfo=None)
    return exp <= ts


async def create_pilot_account(
    session: AsyncSession,
    *,
    username: str,
    pilot_label: str | None = None,
    password: str | None = None,
    business_days: int = 5,
    allowed_cidrs: list[str] | None = None,
    email: str | None = None,
    mfa_required: bool = True,
) -> tuple[User, str, datetime, dict[str, str] | None]:
    username = username.strip()
    if not username:
        raise ValueError("username required")
    existing = await session.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none() is not None:
        raise ValueError("username already exists")

    plain = password or generate_temp_password()
    expires = add_business_days(utc_now(), business_days)
    mfa_secret = generate_totp_secret() if mfa_required else None
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(plain),
        is_active=True,
        is_admin=False,
        role=UserRole.PILOT_READONLY,
        expires_at=expires,
        revoked_at=None,
        allowed_cidrs=allowed_cidrs or None,
        pilot_label=pilot_label or f"Pilot:{username}",
        mfa_required=bool(mfa_required),
        mfa_secret=mfa_secret,
    )
    session.add(user)
    await session.flush()
    enroll = mfa_bundle(secret=mfa_secret, username=username) if mfa_secret else None
    return user, plain, expires, enroll


async def revoke_user(session: AsyncSession, user_id: UUID) -> User | None:
    user = await session.get(User, user_id)
    if user is None:
        return None
    user.is_active = False
    user.revoked_at = utc_now()
    bump_token_version(user)
    await session.flush()
    return user


async def expire_due_pilots(session: AsyncSession) -> int:
    """Deactivate pilot accounts past expires_at. Returns count revoked."""
    now = utc_now()
    result = await session.execute(
        select(User).where(
            User.role == UserRole.PILOT_READONLY,
            User.is_active.is_(True),
            User.expires_at.is_not(None),
            User.expires_at <= now,
        )
    )
    users = list(result.scalars().all())
    for u in users:
        u.is_active = False
        u.revoked_at = now
    if users:
        await session.flush()
    return len(users)


def user_public_dict(user: User, *, include_sensitive: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "role": user.role.value if isinstance(user.role, UserRole) else str(user.role),
        "is_readonly": user.is_readonly,
        "expires_at": user.expires_at.isoformat() if user.expires_at else None,
        "revoked_at": user.revoked_at.isoformat() if user.revoked_at else None,
        "pilot_label": user.pilot_label,
        "allowed_cidrs": user.allowed_cidrs or [],
        "mfa_required": bool(getattr(user, "mfa_required", False)),
        "mfa_enrolled": bool(getattr(user, "mfa_secret", None)),
        "mfa_enforced": bool(getattr(user, "mfa_required", False)),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "last_login_ip": user.last_login_ip,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
    if include_sensitive:
        data["note"] = "password shown only once at creation"
    return data
