from app.core.config import Settings


def test_assemble_database_urls_encodes_special_characters(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SYNC_DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "ma_minsight")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss:word/$2")
    monkeypatch.setenv("POSTGRES_DB", "ma_minsight")
    monkeypatch.setenv("DB_HOST", "postgres")
    monkeypatch.setenv("DB_PORT", "5432")

    settings = Settings(_env_file=None)

    assert settings.sync_database_url == (
        "postgresql://ma_minsight:p%40ss%3Aword%2F%242@postgres:5432/ma_minsight"
    )
    assert settings.database_url == (
        "postgresql+asyncpg://ma_minsight:p%40ss%3Aword%2F%242@postgres:5432/ma_minsight"
    )


def test_explicit_database_url_is_not_overridden(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://custom:secret@db.example:5432/custom",
    )
    monkeypatch.setenv(
        "SYNC_DATABASE_URL",
        "postgresql://custom:secret@db.example:5432/custom",
    )
    monkeypatch.setenv("POSTGRES_PASSWORD", "ignored")
    monkeypatch.setenv("DB_HOST", "postgres")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+asyncpg://custom:secret@db.example:5432/custom"
    assert settings.sync_database_url == "postgresql://custom:secret@db.example:5432/custom"
