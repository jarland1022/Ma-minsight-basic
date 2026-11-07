"""Auth service tests (P0-01: JWT tv/tok, bootstrap paths, start gate)."""

from uuid import uuid4

import jwt
import pytest

from app.core.config import settings
from app.core.security_gate import assert_production_secrets_safe, is_weak_password
from app.services.auth import (
    JWT_ALGORITHM,
    TOKEN_CLASS_BOOTSTRAP,
    TOKEN_CLASS_SESSION,
    create_access_token,
    decode_access_token,
    hash_password,
    is_bootstrap_path_allowed,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_create_and_decode_includes_tv_and_tok() -> None:
    user_id = uuid4()
    token = create_access_token(
        user_id=user_id,
        username="admin",
        is_admin=True,
        role="admin",
        token_version=3,
        token_class=TOKEN_CLASS_SESSION,
    )
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["username"] == "admin"
    assert payload["is_admin"] is True
    assert payload["tv"] == 3
    assert payload["tok"] == TOKEN_CLASS_SESSION


def test_jwt_bootstrap_token_class() -> None:
    token = create_access_token(
        user_id=uuid4(),
        username="admin",
        is_admin=True,
        role="admin",
        token_version=1,
        token_class=TOKEN_CLASS_BOOTSTRAP,
    )
    payload = decode_access_token(token)
    assert payload["tok"] == TOKEN_CLASS_BOOTSTRAP


def test_jwt_invalid_secret() -> None:
    token = create_access_token(user_id=uuid4(), username="u", is_admin=False)
    with pytest.raises(jwt.PyJWTError):
        jwt.decode(token, "wrong-secret", algorithms=[JWT_ALGORITHM])


def test_bootstrap_path_allowlist() -> None:
    assert is_bootstrap_path_allowed("GET", "/api/v1/auth/me")
    assert is_bootstrap_path_allowed("POST", "/api/v1/auth/change-password")
    assert is_bootstrap_path_allowed("POST", "/api/v1/auth/mfa/verify/")
    assert not is_bootstrap_path_allowed("PUT", "/api/v1/system/config")
    assert not is_bootstrap_path_allowed("GET", "/api/v1/users")
    assert not is_bootstrap_path_allowed("POST", "/api/v1/investigations/events/x/reinvestigate")


def test_weak_password_detection() -> None:
    assert is_weak_password("changeme")
    assert is_weak_password("ChangeMe")
    assert not is_weak_password("Str0ng-Enough-Pass!")


def test_production_gate_rejects_allow_insecure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "allow_insecure_defaults", True)
    monkeypatch.setattr(settings, "jwt_secret", "a" * 40)
    monkeypatch.setattr(settings, "api_key", "strong-api-key-value-here")
    monkeypatch.setattr(settings, "admin_initial_password", "Str0ng-Admin-Pass!")
    with pytest.raises(RuntimeError, match="ALLOW_INSECURE_DEFAULTS"):
        assert_production_secrets_safe()


def test_production_gate_rejects_weak_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "allow_insecure_defaults", False)
    monkeypatch.setattr(settings, "jwt_secret", "change-me-jwt-secret-use-32-chars-min")
    monkeypatch.setattr(settings, "api_key", "strong-api-key-value-here")
    monkeypatch.setattr(settings, "admin_initial_password", "Str0ng-Admin-Pass!")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        assert_production_secrets_safe()


def test_production_gate_rejects_weak_admin_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "allow_insecure_defaults", False)
    monkeypatch.setattr(settings, "jwt_secret", "a" * 40)
    monkeypatch.setattr(settings, "api_key", "strong-api-key-value-here")
    monkeypatch.setattr(settings, "admin_initial_password", "changeme")
    with pytest.raises(RuntimeError, match="ADMIN_INITIAL_PASSWORD"):
        assert_production_secrets_safe()


def test_production_gate_ok_with_strong_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "allow_insecure_defaults", False)
    monkeypatch.setattr(settings, "jwt_secret", "a" * 40)
    monkeypatch.setattr(settings, "api_key", "strong-api-key-value-here")
    monkeypatch.setattr(settings, "admin_initial_password", "Str0ng-Admin-Pass!")
    assert_production_secrets_safe()


def test_non_production_skips_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "jwt_secret", "changeme")
    assert_production_secrets_safe()
