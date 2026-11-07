"""P0-01 / T-MFA style unit coverage for enrollment branching helpers."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.services.auth import (
    TOKEN_CLASS_BOOTSTRAP,
    TOKEN_CLASS_SESSION,
    bump_token_version,
    create_access_token,
    decode_access_token,
)


def _user(**kwargs):
    base = {
        "id": uuid4(),
        "username": "admin",
        "is_admin": True,
        "role": "admin",
        "must_change_password": False,
        "mfa_required": True,
        "mfa_secret": None,
        "token_version": 1,
        "expires_at": None,
        "pilot_label": None,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_bump_token_version_increments() -> None:
    user = _user(token_version=2)
    assert bump_token_version(user) == 3
    assert user.token_version == 3


def test_t_mfa_01_new_admin_needs_setup_not_verify_only() -> None:
    """T-MFA-01: no TOTP yet → setup path, not verify-only."""
    user = _user(must_change_password=False, mfa_required=True, mfa_secret=None)
    assert user.mfa_required and not user.mfa_secret
    # verify-only would require mfa_secret; setup is the only valid branch
    assert user.mfa_secret is None


def test_t_mfa_07_password_change_invalidates_old_jwt() -> None:
    """T-MFA-07: bump tv → old JWT tv mismatch."""
    user = _user(token_version=1)
    old = create_access_token(
        user_id=user.id,
        username=user.username,
        is_admin=True,
        role="admin",
        token_version=user.token_version,
        token_class=TOKEN_CLASS_SESSION,
    )
    bump_token_version(user)
    old_tv = decode_access_token(old)["tv"]
    assert old_tv != user.token_version


def test_bootstrap_vs_session_claims() -> None:
    uid = uuid4()
    boot = create_access_token(
        user_id=uid,
        username="admin",
        is_admin=True,
        role="admin",
        token_version=1,
        token_class=TOKEN_CLASS_BOOTSTRAP,
    )
    sess = create_access_token(
        user_id=uid,
        username="admin",
        is_admin=True,
        role="admin",
        token_version=1,
        token_class=TOKEN_CLASS_SESSION,
    )
    assert decode_access_token(boot)["tok"] == TOKEN_CLASS_BOOTSTRAP
    assert decode_access_token(sess)["tok"] == TOKEN_CLASS_SESSION
