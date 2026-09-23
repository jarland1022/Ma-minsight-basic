"""Wazuh Indexer adapter configuration."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field, model_validator


class WazuhIndexerConfig(BaseModel):
    indexer_url: str = Field(..., description="Base URL, e.g. https://wazuh-indexer:9200")
    username_env: str = "WAZUH_INDEXER_USER"
    password_env: str = "WAZUH_INDEXER_PASSWORD"
    index_pattern: str = "wazuh-alerts-*"
    verify_tls: bool = True
    ca_cert_path: str | None = None
    initial_lookback_hours: int = Field(default=24, ge=1, le=168)
    batch_size: int = Field(default=500, ge=1, le=5000)
    request_timeout_seconds: float = 30.0

    def resolve_credentials(self) -> tuple[str, str]:
        username = os.environ.get(self.username_env)
        password = os.environ.get(self.password_env)
        if not username or not password:
            msg = (
                f"Missing Wazuh Indexer credentials: "
                f"set {self.username_env} and {self.password_env}"
            )
            raise ValueError(msg)
        return username, password

    @model_validator(mode="after")
    def normalize_indexer_url(self) -> WazuhIndexerConfig:
        self.indexer_url = self.indexer_url.rstrip("/")
        return self
