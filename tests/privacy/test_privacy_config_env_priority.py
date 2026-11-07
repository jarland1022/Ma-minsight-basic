"""Privacy config priority and fail-closed (P0-06 R-B / AUTH-R3)."""

from __future__ import annotations

import pytest

from app.privacy.config import PrivacyPolicy, _apply_strict, load_privacy_policy
from app.privacy.egress_gateway import EgressDeniedError, EgressGateway
from app.privacy.pseudonym import derive_pseudonym_secret
from app.privacy.types import ContentType, EgressChannel, EgressContext


@pytest.mark.asyncio
async def test_env_force_overrides_system_config_defaults(monkeypatch):
    """PRIVACY_* env must win over code/system defaults (no DB session)."""
    monkeypatch.setenv("PRIVACY_LLM_EGRESS_ENABLED", "false")
    monkeypatch.setenv("PRIVACY_TI_EGRESS_ENABLED", "false")
    monkeypatch.setenv("PRIVACY_EMBED_EGRESS_ENABLED", "true")
    monkeypatch.setenv("PRIVACY_STRICT_MODE", "true")
    monkeypatch.setenv("PRIVACY_CUSTOMER_SCOPE_ID", "tenant-ci")
    monkeypatch.setenv("PRIVACY_PSEUDONYM_SECRET", "unit-test-pseudonym-secret")
    monkeypatch.setattr("app.privacy.config.settings.privacy_pseudonym_secret", "unit-test-pseudonym-secret")
    monkeypatch.setattr("app.privacy.config.settings.privacy_strict_mode", False)
    monkeypatch.setattr("app.privacy.config.settings.privacy_llm_egress_enabled", None)
    monkeypatch.setattr("app.privacy.config.settings.privacy_ti_egress_enabled", None)
    monkeypatch.setattr("app.privacy.config.settings.privacy_embed_egress_enabled", None)
    monkeypatch.setattr("app.privacy.config.settings.app_env", "test")
    monkeypatch.setattr(
        "app.privacy.config.settings.jwt_secret",
        "integration-test-jwt-secret-32chars-min",
    )

    policy = await load_privacy_policy(session=None)
    assert policy.llm_egress_enabled is False
    assert policy.ti_egress_enabled is False
    # strict_mode clamps embed back to False
    assert policy.strict_mode is True
    assert policy.embed_egress_enabled is False
    assert policy.customer_scope_id == "tenant-ci"
    assert policy.allow_username_plaintext is False
    assert policy.pseudonym_secret is not None


@pytest.mark.asyncio
async def test_settings_bool_overrides_system_config_when_env_unset(monkeypatch):
    monkeypatch.delenv("PRIVACY_LLM_EGRESS_ENABLED", raising=False)
    monkeypatch.setattr("app.privacy.config.settings.privacy_llm_egress_enabled", False)
    monkeypatch.setattr("app.privacy.config.settings.privacy_pseudonym_secret", "s")
    monkeypatch.setattr("app.privacy.config.settings.app_env", "test")
    monkeypatch.setattr(
        "app.privacy.config.settings.jwt_secret",
        "integration-test-jwt-secret-32chars-min",
    )
    policy = await load_privacy_policy(session=None)
    assert policy.llm_egress_enabled is False


@pytest.mark.asyncio
async def test_env_force_wins_over_adversarial_system_config(monkeypatch):
    """Even if system_config layer returns True for llm egress, PRIVACY_* env must win."""

    async def _evil_sys_bool(session, key: str, default: bool) -> bool:
        if key == "privacy.llm_egress_enabled":
            return True
        return default

    async def _noop_sys_value(session, key: str, default):
        return default

    monkeypatch.setenv("PRIVACY_LLM_EGRESS_ENABLED", "false")
    monkeypatch.setenv("PRIVACY_PSEUDONYM_SECRET", "unit-test-pseudonym-secret")
    monkeypatch.setattr("app.privacy.config.settings.privacy_pseudonym_secret", "unit-test-pseudonym-secret")
    monkeypatch.setattr("app.privacy.config.settings.privacy_llm_egress_enabled", None)
    monkeypatch.setattr("app.privacy.config.settings.app_env", "test")
    monkeypatch.setattr(
        "app.privacy.config.settings.jwt_secret",
        "integration-test-jwt-secret-32chars-min",
    )
    monkeypatch.setattr("app.privacy.config._sys_bool", _evil_sys_bool)
    monkeypatch.setattr("app.privacy.config._sys_value", _noop_sys_value)

    policy = await load_privacy_policy(session=object())  # type: ignore[arg-type]
    assert policy.llm_egress_enabled is False


def test_strict_mode_clamps_plaintext_flags():
    p = PrivacyPolicy(
        strict_mode=True,
        allow_public_ip_plaintext=True,
        allow_username_plaintext=True,
        allow_hostname_plaintext=True,
        allow_full_url=True,
        allow_consent_plaintext=True,
        wecom_allow_host_user=True,
        embed_egress_enabled=True,
    )
    _apply_strict(p)
    assert p.allow_public_ip_plaintext is False
    assert p.allow_username_plaintext is False
    assert p.embed_egress_enabled is False


def test_production_default_jwt_yields_no_pseudonym_secret():
    secret = derive_pseudonym_secret(
        explicit_secret="",
        jwt_secret="change-me-jwt-secret-use-32-chars-min",
        insecure_jwt_default="change-me-jwt-secret-use-32-chars-min",
        app_env="production",
    )
    assert secret is None


@pytest.mark.asyncio
async def test_missing_pseudonym_secret_fail_closed_send(monkeypatch):
    monkeypatch.delenv("PRIVACY_PSEUDONYM_SECRET", raising=False)
    monkeypatch.setattr("app.privacy.config.settings.privacy_pseudonym_secret", "")
    monkeypatch.setattr("app.privacy.config.settings.app_env", "production")
    monkeypatch.setattr(
        "app.privacy.config.settings.jwt_secret",
        "change-me-jwt-secret-use-32-chars-min",
    )
    monkeypatch.setattr("app.privacy.config.settings.privacy_llm_egress_enabled", True)
    monkeypatch.delenv("PRIVACY_LLM_EGRESS_ENABLED", raising=False)

    policy = await load_privacy_policy(session=None)
    assert policy.pseudonym_secret is None

    gw = EgressGateway()
    with pytest.raises(EgressDeniedError) as ei:
        await gw.send(
            channel=EgressChannel.LLM,
            method="POST",
            url="https://api.deepseek.com/chat/completions",
            json_body={"model": "m", "messages": [{"role": "user", "content": "hi"}]},
            content_type=ContentType.CHAT_MESSAGES,
            context=EgressContext(),
            policy=policy,
        )
    assert "pseudonym_secret_missing" in ei.value.reason or "secret" in ei.value.reason.lower()


@pytest.mark.asyncio
async def test_empty_llm_key_raises_before_http(monkeypatch):
    from app.llm.client import LLMClient

    monkeypatch.setattr("app.llm.client.settings.deepseek_api_key", "")
    client = LLMClient()
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        await client.chat(messages=[{"role": "user", "content": "x"}])
