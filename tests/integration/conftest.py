"""Real Postgres + ASGI TestClient fixtures for P0-08 integration tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from urllib.parse import quote_plus

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_USER = os.environ.get("TEST_DB_USER", os.environ.get("POSTGRES_USER", "ai_sec"))
_PASSWORD = os.environ.get("TEST_DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "AiSec$2026#"))
_DB = os.environ.get("TEST_DB_NAME", os.environ.get("POSTGRES_DB", "ai_sec"))
_HOST = os.environ.get("TEST_DB_HOST", "127.0.0.1")
_ASYNC_URL = f"postgresql+asyncpg://{_USER}:{quote_plus(_PASSWORD)}@{_HOST}:5432/{_DB}"
_SYNC_URL = f"postgresql+psycopg2://{_USER}:{quote_plus(_PASSWORD)}@{_HOST}:5432/{_DB}"

os.environ["DATABASE_URL"] = _ASYNC_URL
os.environ["SYNC_DATABASE_URL"] = _SYNC_URL
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ALLOW_INSECURE_DEFAULTS", "true")
os.environ.setdefault("API_KEY", "AiSecApikey$2026#")
os.environ.setdefault("JWT_SECRET", "integration-test-jwt-secret-32chars-min")
os.environ.setdefault("ADMIN_INITIAL_PASSWORD", "IntegrationTestPass1!")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """ASGI client against real Postgres (function-scoped engine = same event loop)."""
    from app.core.config import settings
    import app.db.session as session_mod
    from app.main import app

    object.__setattr__(settings, "database_url", _ASYNC_URL)
    object.__setattr__(settings, "sync_database_url", _SYNC_URL)
    object.__setattr__(settings, "api_key", os.environ["API_KEY"])
    object.__setattr__(settings, "jwt_secret", os.environ["JWT_SECRET"])
    object.__setattr__(settings, "app_env", "test")

    engine = create_async_engine(_ASYNC_URL, pool_pre_ping=True, pool_size=2)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
            cols = (
                await conn.execute(
                    text(
                        "select column_name from information_schema.columns "
                        "where table_name='audit_logs'"
                    )
                )
            ).fetchall()
            names = {r[0] for r in cols}
            missing = {"result", "correlation_id", "client_ip"} - names
            if missing:
                pytest.skip(f"audit_logs missing columns {missing}; run alembic upgrade head")

            # R-A / AUTH-R1: P0-02 scoped keys require migration 024+
            api_key_cols = (
                await conn.execute(
                    text(
                        "select column_name from information_schema.columns "
                        "where table_name='api_keys'"
                    )
                )
            ).fetchall()
            api_names = {r[0] for r in api_key_cols}
            if "scopes" not in api_names:
                pytest.skip(
                    "api_keys.scopes missing; run alembic upgrade head on the integration test DB "
                    "(see docs/review/P0_06_RESIDUAL_RISK_CLOSURE_PLAN.md R1 / AUTH-R1)"
                )
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"Postgres unavailable for integration tests: {exc}")

    session_mod.engine = engine
    session_mod.async_session_factory = async_sessionmaker(
        engine, expire_on_commit=False
    )

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        await engine.dispose()


@pytest.fixture
def api_headers() -> dict[str, str]:
    """Legacy / scoped API key headers (not sufficient for O-07 high-risk routes)."""
    return {
        "X-API-Key": os.environ["API_KEY"],
        "X-Correlation-ID": "integ-corr-fixed-001",
    }


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient) -> dict[str, str]:
    """JWT admin session headers for high-risk routes (config / pipeline / audit query)."""
    del client  # ensures DB engine from client fixture is ready
    from sqlalchemy import select

    import app.db.session as session_mod
    from app.db.enums import UserRole
    from app.models.system import User
    from app.services.auth import TOKEN_CLASS_SESSION, create_access_token

    async with session_mod.async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.is_admin.is_(True), User.is_active.is_(True)).limit(1)
        )
        user = result.scalar_one_or_none()
        if user is None:
            pytest.skip("No active admin user in integration test DB")
        # Session JWT — not bootstrap — so high-risk routes succeed (O-07).
        if user.must_change_password:
            user.must_change_password = False
            await session.commit()
        token = create_access_token(
            user_id=user.id,
            username=user.username,
            is_admin=True,
            role=getattr(user.role, "value", None) or UserRole.ADMIN.value,
            token_version=int(user.token_version or 1),
            token_class=TOKEN_CLASS_SESSION,
        )
    return {
        "Authorization": f"Bearer {token}",
        "X-Correlation-ID": "integ-corr-fixed-001",
    }
