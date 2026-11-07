"""HMAC-based consistent pseudonymization (not anonymization)."""

from __future__ import annotations

import hashlib
import hmac
from typing import Literal

FieldKind = Literal["user", "host", "ip", "email", "generic"]


class Pseudonymizer:
    """Stable pseudonyms within (secret, scope, field_kind, value).

    Pseudonymization is reversible only with the secret — documentation must
    not claim data is fully anonymous.
    """

    def __init__(self, secret: bytes, *, key_version: int = 1) -> None:
        if not secret:
            raise ValueError("pseudonym secret must be non-empty")
        self._secret = secret
        self.key_version = key_version

    def pseudonymize(self, value: str, *, field_kind: FieldKind, scope: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return raw
        material = f"v{self.key_version}|{scope}|{field_kind}|{raw}".encode("utf-8")
        digest = hmac.new(self._secret, material, hashlib.sha256).hexdigest()[:12]
        prefix = {
            "user": "user",
            "host": "host",
            "ip": "ip",
            "email": "mail",
            "generic": "id",
        }[field_kind]
        return f"{prefix}_{digest}"


def derive_pseudonym_secret(
    *,
    explicit_secret: str,
    jwt_secret: str,
    insecure_jwt_default: str,
    app_env: str,
) -> bytes | None:
    """Resolve pseudonym HMAC key. Returns None → callers must fail-closed."""
    explicit = (explicit_secret or "").strip()
    if explicit:
        return hashlib.sha256(f"minsight-egress-pseudonym-key|{explicit}".encode()).digest()

    jwt = (jwt_secret or "").strip()
    if not jwt:
        return None

    is_prod = app_env.strip().lower() in {"production", "prod"}
    if jwt == insecure_jwt_default and is_prod:
        return None

    # Non-production may derive from jwt_secret so local/dev can investigate;
    # production requires explicit PRIVACY_PSEUDONYM_SECRET or non-default JWT.
    if jwt == insecure_jwt_default:
        # Still derive in dev/test so suites can run; operators should set explicit secret.
        return hashlib.sha256(f"minsight-egress-pseudonym-dev|{jwt}".encode()).digest()

    return hashlib.sha256(f"minsight-egress-pseudonym-v1|{jwt}".encode()).digest()
