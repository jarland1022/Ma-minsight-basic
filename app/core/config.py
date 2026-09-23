"""Application settings loaded from environment variables."""

from __future__ import annotations

from typing import Self
from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_ASYNC_DATABASE_URL = (
    "postgresql+asyncpg://ma_minsight:ma_minsight@localhost:5432/ma_minsight"
)
_DEFAULT_SYNC_DATABASE_URL = "postgresql://ma_minsight:ma_minsight@localhost:5432/ma_minsight"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = _DEFAULT_ASYNC_DATABASE_URL
    sync_database_url: str = _DEFAULT_SYNC_DATABASE_URL
    db_echo: bool = False

    postgres_user: str = "ma_minsight"
    postgres_password: str = ""
    postgres_db: str = "ma_minsight"
    db_host: str = "localhost"
    db_port: int = 5432

    redis_url: str = "redis://localhost:6379/0"

    api_key: str = "change-me-in-production"

    wazuh_indexer_user: str = ""
    wazuh_indexer_password: str = ""

    ingestion_max_batches_per_run: int = 10

    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"

    wecom_corp_id: str = ""
    wecom_agent_id: str = "0"
    wecom_secret: str = ""
    wecom_webhook_url: str = ""
    wecom_callback_token: str = ""
    wecom_encoding_aes_key: str = ""

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    abuseipdb_api_key: str = ""
    abuseipdb_max_age_days: int = 90
    greynoise_api_key: str = ""
    threat_intel_sync_window_days: int = 7
    threat_intel_sync_limit: int = 200
    threat_intel_cache_ttl_hours: int = 24
    threat_intel_skip_private_ips: bool = True
    threat_intel_http_timeout_seconds: float = 30.0

    geolite2_city_path: str = ""

    jwt_secret: str = "change-me-jwt-secret-use-32-chars-min"
    jwt_expire_hours: int = 8
    admin_initial_password: str = "changeme"

    @model_validator(mode="after")
    def assemble_database_urls(self) -> Self:
        """Build DB URLs from discrete vars when compose injects POSTGRES_* + DB_HOST."""
        if (
            self.database_url != _DEFAULT_ASYNC_DATABASE_URL
            or self.sync_database_url != _DEFAULT_SYNC_DATABASE_URL
        ):
            return self
        if self.db_host in {"localhost", "127.0.0.1"} and not self.postgres_password:
            return self

        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        base = f"{user}:{password}@{self.db_host}:{self.db_port}/{self.postgres_db}"
        self.database_url = f"postgresql+asyncpg://{base}"
        self.sync_database_url = f"postgresql://{base}"
        return self


settings = Settings()
