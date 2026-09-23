from configparser import ConfigParser

import pytest
from sqlalchemy import create_engine


def test_percent_encoded_db_url_breaks_configparser() -> None:
    url = "postgresql://ai_sec:AiSec%24%242026%23@postgres:5432/ai_sec"
    cfg = ConfigParser()
    cfg.add_section("alembic")

    with pytest.raises(ValueError, match="invalid interpolation syntax"):
        cfg.set("alembic", "sqlalchemy.url", url)


def test_create_engine_accepts_percent_encoded_password() -> None:
    url = "postgresql://ai_sec:AiSec%24%242026%23@postgres:5432/ai_sec"
    engine = create_engine(url)

    assert engine.url.username == "ai_sec"
    assert engine.url.password == "AiSec$$2026#"
    assert engine.url.database == "ai_sec"
