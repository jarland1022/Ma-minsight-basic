"""R-A: alembic upgrade head against integration-test DB only (default ai_sec@127.0.0.1)."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from alembic import command
from alembic.config import Config

# Bind settings before alembic env imports them.
_USER = os.environ.get("TEST_DB_USER", os.environ.get("POSTGRES_USER", "ai_sec"))
_PASSWORD = os.environ.get("TEST_DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "AiSec$2026#"))
_DB = os.environ.get("TEST_DB_NAME", os.environ.get("POSTGRES_DB", "ai_sec"))
_HOST = os.environ.get("TEST_DB_HOST", "127.0.0.1")

_SYNC = f"postgresql+psycopg2://{_USER}:{quote_plus(_PASSWORD)}@{_HOST}:5432/{_DB}"
_ASYNC = f"postgresql+asyncpg://{_USER}:{quote_plus(_PASSWORD)}@{_HOST}:5432/{_DB}"
os.environ["SYNC_DATABASE_URL"] = _SYNC
os.environ["DATABASE_URL"] = _ASYNC

from app.core.config import settings  # noqa: E402

object.__setattr__(settings, "sync_database_url", _SYNC)
object.__setattr__(settings, "database_url", _ASYNC)


def main() -> None:
    if _HOST not in {"127.0.0.1", "localhost"}:
        raise SystemExit(f"Refusing upgrade: host {_HOST!r} is not local test host")
    if _DB in {"prod", "production"}:
        raise SystemExit(f"Refusing upgrade: database name {_DB!r} looks like production")

    root = Path(__file__).resolve().parents[1]
    print(f"Upgrading ONLY local test DB host={_HOST} db={_DB} user={_USER}")
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(cfg, "head")
    print("alembic upgrade head OK")


if __name__ == "__main__":
    main()
