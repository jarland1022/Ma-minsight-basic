"""P0-02 / T-KEY-01..09 + Pilot MFA default + legacy high-risk block."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.api_key_scopes import (
    can_run_pipeline,
    is_high_risk_request,
    scoped_key_allows_request,
    validate_scopes,
)
from app.services.api_keys import (
    api_key_public_dict,
    generate_api_key_plaintext,
    hash_api_key,
    resolve_scoped_api_key,
)
from app.services.auth import AuthContext
from app.services.pilot_accounts import create_pilot_account


def test_t_key_01_hash_only_not_plaintext() -> None:
    plain, prefix = generate_api_key_plaintext()
    digest = hash_api_key(plain)
    assert plain.startswith("msk_")
    assert prefix.startswith("msk_")
    assert digest != plain
    assert len(digest) == 64
    assert plain not in digest


def test_t_key_02_public_dict_never_contains_secret() -> None:
    plain, prefix = generate_api_key_plaintext()
    row = SimpleNamespace(
        id=uuid4(),
        name="k",
        key_prefix=prefix,
        scopes=["events:read"],
        is_active=True,
        expires_at=None,
        revoked_at=None,
        last_used_at=None,
        rotated_from_id=None,
        user_id=uuid4(),
        created_at=datetime.now(UTC),
        key_hash=hash_api_key(plain),
    )
    pub = api_key_public_dict(row)  # type: ignore[arg-type]
    blob = str(pub)
    assert plain not in blob
    assert "api_key" not in pub
    assert pub["key_prefix"] == prefix


def test_t_key_07_scopes_cannot_elevate_admin() -> None:
    with pytest.raises(ValueError, match="admin"):
        validate_scopes(["admin"])
    with pytest.raises(ValueError, match="admin"):
        validate_scopes(["role:admin"])
    with pytest.raises(ValueError, match="not allowed"):
        validate_scopes(["*"])
    with pytest.raises(ValueError, match="not allowed|Unknown"):
        validate_scopes(["users:write"])
    assert validate_scopes(["events:read", "ingestion:pull"]) == [
        "events:read",
        "ingestion:pull",
    ]


def test_t_key_08_legacy_and_scoped_blocked_from_high_risk() -> None:
    assert is_high_risk_request("PUT", "/api/v1/system/config/foo")
    assert is_high_risk_request("POST", "/api/v1/users/pilots")
    assert is_high_risk_request("POST", "/api/v1/api-keys")
    assert is_high_risk_request("POST", "/api/v1/license/import")
    assert is_high_risk_request("POST", "/api/v1/whitelist-rules/x/enable-suppression")
    assert not is_high_risk_request("GET", "/api/v1/events")
    assert not is_high_risk_request("POST", "/api/v1/console/run/triage")


def test_t_key_09_prefix_identifies_not_authenticates() -> None:
    plain, prefix = generate_api_key_plaintext()
    assert len(prefix) <= 16
    assert plain != prefix
    assert plain.startswith(prefix) or prefix in plain


def test_scoped_key_limited_to_granted_paths() -> None:
    scopes = ["events:read"]
    assert scoped_key_allows_request("GET", "/api/v1/events", scopes)
    assert scoped_key_allows_request("GET", "/api/v1/events/abc", scopes)
    assert not scoped_key_allows_request("GET", "/api/v1/dashboard", scopes)
    assert not scoped_key_allows_request("POST", "/api/v1/disposition/x/confirm", scopes)
    assert not scoped_key_allows_request("PUT", "/api/v1/system/config/x", scopes)


def test_scoped_pipeline_and_ingestion_scopes() -> None:
    assert scoped_key_allows_request(
        "POST", "/api/v1/console/run/triage", ["pipeline:run:triage"]
    )
    assert not scoped_key_allows_request(
        "POST", "/api/v1/console/run/investigation", ["pipeline:run:triage"]
    )
    assert scoped_key_allows_request(
        "POST", "/api/v1/ingestion/sources/x/pull", ["ingestion:pull"]
    )


def test_legacy_pipeline_matrix_o10() -> None:
    assert can_run_pipeline(
        is_admin=False,
        role="operator",
        via_legacy_api_key=True,
        scopes=None,
        pipeline="triage",
    )
    assert not can_run_pipeline(
        is_admin=False,
        role="operator",
        via_legacy_api_key=True,
        scopes=None,
        pipeline="investigation",
    )
    assert can_run_pipeline(
        is_admin=True,
        role="admin",
        via_legacy_api_key=False,
        scopes=None,
        pipeline="investigation",
    )


def test_jwt_admin_property_excludes_api_keys() -> None:
    legacy = AuthContext(
        user_id=None,
        username="legacy_api_key",
        is_admin=False,
        via_api_key=True,
        via_legacy_api_key=True,
    )
    scoped = AuthContext(
        user_id=uuid4(),
        username="api_key:msk_abcd",
        is_admin=False,
        via_api_key=True,
        scopes=["events:read"],
    )
    admin = AuthContext(
        user_id=uuid4(),
        username="admin",
        is_admin=True,
        via_api_key=False,
    )
    assert not legacy.is_jwt_admin
    assert not scoped.is_jwt_admin
    assert admin.is_jwt_admin


@pytest.mark.asyncio
async def test_t_key_03_04_expired_and_revoked_rejected() -> None:
    plain, prefix = generate_api_key_plaintext()
    digest = hash_api_key(plain)

    expired = SimpleNamespace(
        id=uuid4(),
        key_hash=digest,
        key_prefix=prefix,
        is_active=True,
        revoked_at=None,
        expires_at=datetime.now(UTC) - timedelta(hours=1),
        scopes=["events:read"],
        last_used_at=None,
    )
    revoked = SimpleNamespace(
        id=uuid4(),
        key_hash=digest,
        key_prefix=prefix,
        is_active=False,
        revoked_at=datetime.now(UTC),
        expires_at=None,
        scopes=["events:read"],
        last_used_at=None,
    )

    async def _one(row):
        session = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = row
        session.execute = AsyncMock(return_value=result)
        return await resolve_scoped_api_key(session, plain)

    assert await _one(expired) is None
    assert await _one(revoked) is None


@pytest.mark.asyncio
async def test_t_key_05_rotate_revokes_old_semantics() -> None:
    """Rotate helper marks old inactive + revoked_at immediately."""
    from app.services.api_keys import rotate_api_key

    old_id = uuid4()
    old = SimpleNamespace(
        id=old_id,
        user_id=uuid4(),
        name="k",
        scopes=["events:read"],
        expires_at=None,
        is_active=True,
        revoked_at=None,
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=old)
    session.add = MagicMock()
    session.flush = AsyncMock()

    result = await rotate_api_key(session, key_id=old_id)
    assert result is not None
    new_row, plaintext = result
    assert old.is_active is False
    assert old.revoked_at is not None
    assert plaintext.startswith("msk_")
    assert new_row.rotated_from_id == old_id
    assert "msk_" not in str(new_row.key_hash)


def test_t_key_06_audit_redacts_api_key_material() -> None:
    from app.services.audit_redact import redact_for_audit

    plain, _ = generate_api_key_plaintext()
    out = redact_for_audit(
        {
            "api_key": plain,
            "authorization": f"Bearer {plain}",
            "key_prefix": "msk_abcd1234",
        }
    )
    assert out["api_key"] == "***REDACTED***"
    assert plain not in str(out["authorization"])
    assert out["key_prefix"] == "msk_abcd1234"


def test_pilot_mfa_default_true() -> None:
    import inspect

    from app.api.routes.users import CreatePilotRequest

    sig = inspect.signature(create_pilot_account)
    assert sig.parameters["mfa_required"].default is True
    assert CreatePilotRequest.model_fields["mfa_required"].default is True


def test_legacy_disabled_config_flag_exists() -> None:
    from app.core.config import settings

    assert hasattr(settings, "legacy_api_key_enabled")
