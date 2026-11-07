"""Scoped API key create / verify / rotate / revoke (P0-02)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.datetime_utils import as_naive_utc, utc_now
from app.models.system import ApiKey
from app.services.api_key_scopes import validate_scopes

KEY_PREFIX_TOKEN = "msk_"


def hash_api_key(plaintext: str) -> str:
    """Hash only — never store plaintext (T-KEY-01)."""
    pepper = settings.jwt_secret or ""
    return hashlib.sha256(f"{pepper}:{plaintext}".encode("utf-8")).hexdigest()


def generate_api_key_plaintext() -> tuple[str, str]:
    """Return (plaintext, key_prefix). Prefix is for support display only (T-KEY-09)."""
    body = secrets.token_urlsafe(32)
    plaintext = f"{KEY_PREFIX_TOKEN}{body}"
    # show msk_ + first 8 of body
    prefix = f"{KEY_PREFIX_TOKEN}{body[:8]}"
    return plaintext, prefix[:16]


def api_key_public_dict(row: ApiKey) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "key_prefix": row.key_prefix,
        "scopes": list(row.scopes or []),
        "is_active": bool(row.is_active),
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        "rotated_from_id": str(row.rotated_from_id) if row.rotated_from_id else None,
        "user_id": str(row.user_id),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def create_api_key(
    session: AsyncSession,
    *,
    user_id: UUID,
    name: str,
    scopes: list[str],
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    validated = validate_scopes(scopes)
    plaintext, prefix = generate_api_key_plaintext()
    row = ApiKey(
        id=uuid4(),
        user_id=user_id,
        name=name.strip(),
        key_hash=hash_api_key(plaintext),
        key_prefix=prefix,
        scopes=validated,
        is_active=True,
        expires_at=expires_at,
        revoked_at=None,
    )
    session.add(row)
    await session.flush()
    return row, plaintext


async def revoke_api_key(session: AsyncSession, key_id: UUID) -> ApiKey | None:
    row = await session.get(ApiKey, key_id)
    if row is None:
        return None
    row.is_active = False
    row.revoked_at = utc_now()
    await session.flush()
    return row


async def rotate_api_key(
    session: AsyncSession,
    *,
    key_id: UUID,
    scopes: list[str] | None = None,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str] | None:
    old = await session.get(ApiKey, key_id)
    if old is None:
        return None
    new_scopes = validate_scopes(scopes if scopes is not None else list(old.scopes or []))
    # Revoke old immediately (T-KEY-05)
    old.is_active = False
    old.revoked_at = utc_now()
    plaintext, prefix = generate_api_key_plaintext()
    new = ApiKey(
        id=uuid4(),
        user_id=old.user_id,
        name=old.name,
        key_hash=hash_api_key(plaintext),
        key_prefix=prefix,
        scopes=new_scopes,
        is_active=True,
        expires_at=expires_at if expires_at is not None else old.expires_at,
        revoked_at=None,
        rotated_from_id=old.id,
    )
    session.add(new)
    await session.flush()
    return new, plaintext


async def list_api_keys(session: AsyncSession, *, user_id: UUID | None = None) -> list[ApiKey]:
    stmt = select(ApiKey).order_by(ApiKey.created_at.desc())
    if user_id is not None:
        stmt = stmt.where(ApiKey.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def resolve_scoped_api_key(session: AsyncSession, plaintext: str) -> ApiKey | None:
    """Lookup by hash; enforce active / not revoked / not expired (T-KEY-03/04)."""
    if not plaintext or not plaintext.startswith(KEY_PREFIX_TOKEN):
        # Still allow verifying keys that use msk_ only for scoped; legacy is separate.
        digest = hash_api_key(plaintext)
    else:
        digest = hash_api_key(plaintext)

    result = await session.execute(select(ApiKey).where(ApiKey.key_hash == digest))
    row = result.scalar_one_or_none()
    if row is None:
        return None
    if not row.is_active or row.revoked_at is not None:
        return None
    if row.expires_at is not None and as_naive_utc(row.expires_at) <= utc_now():
        return None
    row.last_used_at = utc_now()
    return row
