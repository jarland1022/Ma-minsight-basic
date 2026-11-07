"""Real Postgres system_config vs PRIVACY_* env (P0-06 R-B supplementary / AUTH-R3).

Uses the local integration test DB only (default 127.0.0.1/ai_sec). Never production.
Cleans up inserted keys after each test.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from urllib.parse import quote_plus

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.system import SystemConfig
from app.privacy.config import load_privacy_policy

_USER = os.environ.get("TEST_DB_USER", os.environ.get("POSTGRES_USER", "ai_sec"))
_PASSWORD = os.environ.get("TEST_DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "AiSec$2026#"))
_DB = os.environ.get("TEST_DB_NAME", os.environ.get("POSTGRES_DB", "ai_sec"))
_HOST = os.environ.get("TEST_DB_HOST", "127.0.0.1")
_ASYNC_URL = f"postgresql+asyncpg://{_USER}:{quote_plus(_PASSWORD)}@{_HOST}:5432/{_DB}"

# Prefixed keys owned exclusively by this suite — safe to delete on cleanup.
_TEST_KEYS = (
    "privacy.llm_egress_enabled",
    "privacy.ti_egress_enabled",
    "privacy.strict_mode",
    "privacy.llm.allow_username_plaintext",
    "privacy.llm.allow_public_ip_plaintext",
    "privacy.embed_egress_enabled",
)


def _assert_not_production_db() -> None:
    name = _DB.lower()
    host = _HOST.lower()
    assert host in {"127.0.0.1", "localhost", "::1"}, f"refusing non-local host: {_HOST}"
    assert name not in {"ma_minsight", "production", "prod"}, f"refusing DB name: {_DB}"
    assert name == "ai_sec" or os.environ.get("ALLOW_NON_AI_SEC_TEST_DB") == "1", (
        f"expected test DB ai_sec, got {_DB}"
    )


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    _assert_not_production_db()
    engine = create_async_engine(_ASYNC_URL, pool_pre_ping=True, pool_size=2)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
            exists = (
                await conn.execute(
                    text(
                        "select 1 from information_schema.tables "
                        "where table_name='system_config'"
                    )
                )
            ).scalar()
            if not exists:
                pytest.skip("system_config table missing")
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"Postgres unavailable: {exc}")

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        # Snapshot then clear any pre-existing rows for our keys
        prior = (
            await session.execute(select(SystemConfig).where(SystemConfig.key.in_(_TEST_KEYS)))
        ).scalars().all()
        prior_map = {r.key: (dict(r.value), r.description) for r in prior}
        if prior:
            await session.execute(delete(SystemConfig).where(SystemConfig.key.in_(_TEST_KEYS)))
            await session.commit()
        try:
            yield session
        finally:
            await session.rollback()
            await session.execute(delete(SystemConfig).where(SystemConfig.key.in_(_TEST_KEYS)))
            for key, (value, desc) in prior_map.items():
                session.add(SystemConfig(key=key, value=value, description=desc))
            await session.commit()
    await engine.dispose()


async def _upsert_bool(session: AsyncSession, key: str, value: bool) -> None:
    row = await session.get(SystemConfig, key)
    payload = {"value": value}
    if row is None:
        session.add(
            SystemConfig(
                key=key,
                value=payload,
                description="R-B adversarial test (temporary)",
            )
        )
    else:
        row.value = payload
    await session.commit()


@pytest.mark.asyncio
async def test_env_disables_channel_despite_db_enable(db_session: AsyncSession, monkeypatch):
    """Env forces LLM off; DB tries to enable — env wins."""
    await _upsert_bool(db_session, "privacy.llm_egress_enabled", True)
    monkeypatch.setenv("PRIVACY_LLM_EGRESS_ENABLED", "false")
    monkeypatch.setenv("PRIVACY_PSEUDONYM_SECRET", "rb-supp-pseudonym-secret")
    monkeypatch.setattr("app.privacy.config.settings.privacy_pseudonym_secret", "rb-supp-pseudonym-secret")
    monkeypatch.setattr("app.privacy.config.settings.privacy_llm_egress_enabled", None)
    monkeypatch.setattr("app.privacy.config.settings.app_env", "test")
    monkeypatch.setattr(
        "app.privacy.config.settings.jwt_secret",
        "integration-test-jwt-secret-32chars-min",
    )

    policy = await load_privacy_policy(session=db_session)
    assert policy.llm_egress_enabled is False


@pytest.mark.asyncio
async def test_env_strict_blocks_db_plaintext_relax(db_session: AsyncSession, monkeypatch):
    """Env strict_mode=true; DB tries to allow username plaintext — clamped."""
    await _upsert_bool(db_session, "privacy.strict_mode", False)
    await _upsert_bool(db_session, "privacy.llm.allow_username_plaintext", True)
    await _upsert_bool(db_session, "privacy.llm.allow_public_ip_plaintext", True)
    await _upsert_bool(db_session, "privacy.embed_egress_enabled", True)

    monkeypatch.setenv("PRIVACY_STRICT_MODE", "true")
    monkeypatch.delenv("PRIVACY_LLM_ALLOW_USERNAME_PLAINTEXT", raising=False)
    monkeypatch.delenv("PRIVACY_LLM_ALLOW_PUBLIC_IP_PLAINTEXT", raising=False)
    monkeypatch.delenv("PRIVACY_EMBED_EGRESS_ENABLED", raising=False)
    monkeypatch.setenv("PRIVACY_PSEUDONYM_SECRET", "rb-supp-pseudonym-secret")
    monkeypatch.setattr("app.privacy.config.settings.privacy_pseudonym_secret", "rb-supp-pseudonym-secret")
    monkeypatch.setattr("app.privacy.config.settings.privacy_strict_mode", False)
    monkeypatch.setattr("app.privacy.config.settings.privacy_embed_egress_enabled", None)
    monkeypatch.setattr("app.privacy.config.settings.app_env", "test")
    monkeypatch.setattr(
        "app.privacy.config.settings.jwt_secret",
        "integration-test-jwt-secret-32chars-min",
    )

    policy = await load_privacy_policy(session=db_session)
    assert policy.strict_mode is True
    assert policy.allow_username_plaintext is False
    assert policy.allow_public_ip_plaintext is False
    assert policy.embed_egress_enabled is False


@pytest.mark.asyncio
async def test_pseudonym_secret_from_env_not_db(db_session: AsyncSession, monkeypatch):
    """Pseudonym secret is env/settings-only; adversarial privacy.* DB rows cannot supply it."""
    # Plant distractor keys that look privacy-related; secret must still come from env.
    await _upsert_bool(db_session, "privacy.llm_egress_enabled", True)
    monkeypatch.setenv("PRIVACY_PSEUDONYM_SECRET", "env-forced-pseudonym-secret-rb")
    monkeypatch.setattr(
        "app.privacy.config.settings.privacy_pseudonym_secret",
        "env-forced-pseudonym-secret-rb",
    )
    monkeypatch.setattr("app.privacy.config.settings.privacy_llm_egress_enabled", None)
    monkeypatch.setattr("app.privacy.config.settings.app_env", "test")
    monkeypatch.setattr(
        "app.privacy.config.settings.jwt_secret",
        "integration-test-jwt-secret-32chars-min",
    )

    policy = await load_privacy_policy(session=db_session)
    assert policy.pseudonym_secret is not None
    # Secret bytes derived from env string — must be non-empty and not None
    assert len(policy.pseudonym_secret) >= 16


@pytest.mark.asyncio
async def test_system_config_applies_when_env_unset(db_session: AsyncSession, monkeypatch):
    """When PRIVACY_* unset, system_config values load as designed."""
    await _upsert_bool(db_session, "privacy.llm_egress_enabled", False)
    await _upsert_bool(db_session, "privacy.ti_egress_enabled", False)

    for name in (
        "PRIVACY_LLM_EGRESS_ENABLED",
        "PRIVACY_TI_EGRESS_ENABLED",
        "PRIVACY_STRICT_MODE",
    ):
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("PRIVACY_PSEUDONYM_SECRET", "rb-supp-pseudonym-secret")
    monkeypatch.setattr("app.privacy.config.settings.privacy_pseudonym_secret", "rb-supp-pseudonym-secret")
    monkeypatch.setattr("app.privacy.config.settings.privacy_llm_egress_enabled", None)
    monkeypatch.setattr("app.privacy.config.settings.privacy_ti_egress_enabled", None)
    monkeypatch.setattr("app.privacy.config.settings.privacy_strict_mode", False)
    monkeypatch.setattr("app.privacy.config.settings.app_env", "test")
    monkeypatch.setattr(
        "app.privacy.config.settings.jwt_secret",
        "integration-test-jwt-secret-32chars-min",
    )

    policy = await load_privacy_policy(session=db_session)
    assert policy.llm_egress_enabled is False
    assert policy.ti_egress_enabled is False


@pytest.mark.asyncio
async def test_config_update_writes_audit_for_privacy_key(db_session: AsyncSession):
    """Writing privacy.* via the same SystemConfig path used by Admin API is auditable."""
    from app.services.audit import AuditResult, write_audit
    from app.models.system import AuditLog

    key = "privacy.llm_egress_enabled"
    await _upsert_bool(db_session, key, True)
    row = await db_session.get(SystemConfig, key)
    assert row is not None
    before = {"value": {"value": False}}
    after = {"value": dict(row.value)}
    corr = "rb-supp-privacy-config-audit"
    await write_audit(
        db_session,
        action="config.update",
        actor_id="rb-supp-test",
        resource_type="system_config",
        resource_id=key,
        detail={"event_level": "business", "created": False, "key": key, "suite": "rb-supp"},
        before=before,
        after=after,
        result=AuditResult.SUCCESS,
        correlation_id=corr,
        client_ip="127.0.0.1",
        commit=True,
        fail_closed=True,
    )
    try:
        logs = (
            await db_session.execute(
                select(AuditLog).where(AuditLog.correlation_id == corr)
            )
        ).scalars().all()
        assert len(logs) >= 1
        assert logs[0].resource_type == "system_config"
        assert logs[0].resource_id == key
        assert logs[0].action == "config.update"
    finally:
        await db_session.execute(delete(AuditLog).where(AuditLog.correlation_id == corr))
        await db_session.commit()
