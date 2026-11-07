"""Application settings loaded from environment variables."""

from __future__ import annotations

from typing import Self
from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_ASYNC_DATABASE_URL = (
    "postgresql+asyncpg://ma_minsight:ma_minsight@localhost:5432/ma_minsight"
)
# Explicit psycopg2: SQLAlchemy 2.1+ defaults bare "postgresql://" to psycopg v3.
_DEFAULT_SYNC_DATABASE_URL = (
    "postgresql+psycopg2://ma_minsight:ma_minsight@localhost:5432/ma_minsight"
)


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

    # production | development | test — production refuses weak secrets at startup
    app_env: str = "development"
    allow_insecure_defaults: bool = False

    login_rate_limit_max: int = 5
    login_rate_limit_window_seconds: int = 900
    bootstrap_token_ttl_minutes: int = 30

    # P0-02 legacy env API_KEY compatibility (D-KEY-02/04). Disable without removing env.
    # Production may set LEGACY_API_KEY_ENABLED=false after cutover; never restores high-risk.
    legacy_api_key_enabled: bool = True

    # P0-06 privacy / egress (backend-enforced; see app/privacy/)
    privacy_pseudonym_secret: str = ""
    privacy_strict_mode: bool = False
    privacy_llm_egress_enabled: bool | None = None
    privacy_ti_egress_enabled: bool | None = None
    privacy_wecom_egress_enabled: bool | None = None
    privacy_embed_egress_enabled: bool | None = None
    privacy_webhook_egress_enabled: bool | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() in {"production", "prod"}

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
        self.sync_database_url = f"postgresql+psycopg2://{base}"
        return self


settings = Settings()
