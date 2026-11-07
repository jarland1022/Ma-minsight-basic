"""Apply pending alembic migrations against host-mapped Postgres."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from alembic import command
from alembic.config import Config


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    user = os.environ.get("POSTGRES_USER", "ai_sec")
    password = os.environ.get("POSTGRES_PASSWORD", "AiSec$2026#")
    db = os.environ.get("POSTGRES_DB", "ai_sec")
    sync_url = f"postgresql+psycopg2://{user}:{quote_plus(password)}@127.0.0.1:5432/{db}"

    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")
    print("upgraded to head using", sync_url.split("@")[-1])


if __name__ == "__main__":
    main()
