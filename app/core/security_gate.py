"""Production startup secret checks (P0-01)."""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_WEAK_JWT = frozenset(
    {
        "change-me-jwt-secret-use-32-chars-min",
        "changeme",
        "secret",
        "jwt-secret",
    }
)

_WEAK_API_KEYS = frozenset(
    {
        "change-me-in-production",
        "changeme",
        "change-me",
        "api-key",
    }
)

_WEAK_PASSWORDS = frozenset(
    {
        "changeme",
        "change-me",
        "admin",
        "password",
        "admin123",
        "12345678",
    }
)


def is_weak_password(password: str) -> bool:
    return password.strip().lower() in _WEAK_PASSWORDS


def assert_production_secrets_safe() -> None:
    """Refuse to start production with insecure defaults.

    Dev/test may use ALLOW_INSECURE_DEFAULTS=true. That flag is rejected in production.
    """
    if not settings.is_production:
        return

    if settings.allow_insecure_defaults:
        raise RuntimeError(
            "ALLOW_INSECURE_DEFAULTS cannot be enabled when APP_ENV=production"
        )

    jwt_secret = (settings.jwt_secret or "").strip()
    if not jwt_secret or jwt_secret in _WEAK_JWT or len(jwt_secret) < 32:
        raise RuntimeError(
            "Production requires a strong JWT_SECRET (min 32 chars, not a known default)"
        )

    api_key = (settings.api_key or "").strip()
    if not api_key or api_key.lower() in _WEAK_API_KEYS:
        raise RuntimeError(
            "Production requires a strong API_KEY (not a known default like change-me-in-production)"
        )

    initial = (settings.admin_initial_password or "").strip()
    if not initial or is_weak_password(initial):
        raise RuntimeError(
            "Production requires a strong ADMIN_INITIAL_PASSWORD "
            "(not changeme / other weak defaults). Deliver via env or Docker Secret."
        )

    logger.info("Production security gate passed (JWT_SECRET / API_KEY / ADMIN_INITIAL_PASSWORD)")
