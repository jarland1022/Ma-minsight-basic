"""Redact secrets / credentials from audit payloads (P0-08)."""

from __future__ import annotations

import re
from typing import Any

_REDACTED = "***REDACTED***"

# Exact / substring key match (case-insensitive).
_SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "authorization",
    "jwt",
    "bearer",
    "mfa_secret",
    "totp",
    "credential",
    "webhook_secret",
    "encoding_aes_key",
    "deepseek_api_key",
    "openai_api_key",
    "abuseipdb",
    "greynoise",
    "client_secret",
    "refresh_token",
    "session_id",
)

_BEARER_RE = re.compile(r"(Bearer\s+)(\S+)", re.IGNORECASE)
_KEY_VALUE_RE = re.compile(
    r"(?i)\b(api[_-]?key|password|secret|token)\b(\s*[:=]\s*)([^\s,;]+)"
)


def _key_is_sensitive(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(frag in lowered for frag in _SENSITIVE_KEY_FRAGMENTS)


def redact_string(value: str) -> str:
    out = _BEARER_RE.sub(r"\1" + _REDACTED, value)
    out = _KEY_VALUE_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{_REDACTED}", out)
    return out


def redact_for_audit(value: Any) -> Any:
    """Recursively redact sensitive keys and credential-like strings."""
    if value is None:
        return None
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if _key_is_sensitive(key):
                out[key] = _REDACTED
            else:
                out[key] = redact_for_audit(v)
        return out
    if isinstance(value, list):
        return [redact_for_audit(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_for_audit(v) for v in value)
    if isinstance(value, str):
        return redact_string(value)
    return value
