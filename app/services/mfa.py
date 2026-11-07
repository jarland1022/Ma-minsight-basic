"""TOTP MFA helpers (RFC 6238) for console / pilot accounts."""

from __future__ import annotations

import base64
import io
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
import pyotp
import qrcode
from qrcode.image.pil import PilImage

from app.core.config import settings
from app.services.auth import JWT_ALGORITHM

MFA_TOKEN_TTL_MINUTES = 5
ISSUER = "MA-MinSight"


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(*, secret: str, username: str, issuer: str = ISSUER) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def verify_totp(secret: str, code: str, *, valid_window: int = 1) -> bool:
    cleaned = (code or "").strip().replace(" ", "")
    if not cleaned.isdigit():
        return False
    totp = pyotp.TOTP(secret)
    return bool(totp.verify(cleaned, valid_window=valid_window))


def qr_png_data_url(otpauth_uri: str) -> str:
    img: PilImage = qrcode.make(otpauth_uri)  # type: ignore[assignment]
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def create_mfa_token(
    *,
    user_id: UUID,
    username: str,
    purpose: str,
    pending_secret: str | None = None,
) -> str:
    """Short-lived token used between password check and TOTP success."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "typ": "mfa",
        "purpose": purpose,
        "sub": str(user_id),
        "username": username,
        "exp": now + timedelta(minutes=MFA_TOKEN_TTL_MINUTES),
        "iat": now,
    }
    if pending_secret:
        payload["pending_secret"] = pending_secret
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_mfa_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    if payload.get("typ") != "mfa":
        raise jwt.InvalidTokenError("not an MFA challenge token")
    return payload


def mfa_bundle(*, secret: str, username: str) -> dict[str, str]:
    uri = provisioning_uri(secret=secret, username=username)
    return {
        "mfa_secret": secret,
        "otpauth_uri": uri,
        "qr_png_data_url": qr_png_data_url(uri),
    }
