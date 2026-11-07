"""Backend-authoritative privacy / egress configuration.

Priority (highest first):
  1. Environment variable force (PRIVACY_*)
  2. strict_mode constraints
  3. system_config privacy.* (when session provided)
  4. Code defaults
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.privacy.pseudonym import derive_pseudonym_secret

_INSECURE_JWT = "change-me-jwt-secret-use-32-chars-min"

POLICY_ID = "minsight-egress-v1"
POLICY_VERSION = 1


def _env_bool(name: str) -> bool | None:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str) -> list[str] | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(x).strip().rstrip("/") for x in data]
        except json.JSONDecodeError:
            pass
    return [p.strip().rstrip("/") for p in raw.split(",") if p.strip()]


@dataclass
class PrivacyPolicy:
    policy_id: str = POLICY_ID
    policy_version: int = POLICY_VERSION
    strict_mode: bool = False
    llm_egress_enabled: bool = True
    ti_egress_enabled: bool = True
    wecom_egress_enabled: bool = True
    embed_egress_enabled: bool = False
    webhook_egress_enabled: bool = True
    allow_public_ip_plaintext: bool = False
    allow_username_plaintext: bool = False
    allow_hostname_plaintext: bool = False
    allow_full_url: bool = False
    allow_consent_plaintext: bool = False
    wecom_allow_host_user: bool = False
    allowed_llm_base_urls: list[str] = field(default_factory=list)
    pseudonym_scope_mode: str = "investigation"  # investigation | tenant
    customer_scope_id: str = "default"
    # Resolved at load time
    pseudonym_secret: bytes | None = None

    def channel_enabled(self, channel: str) -> bool:
        mapping = {
            "llm": self.llm_egress_enabled,
            "ti": self.ti_egress_enabled,
            "wecom": self.wecom_egress_enabled,
            "embed": self.embed_egress_enabled,
            "webhook": self.webhook_egress_enabled,
            "skill_http": False,  # fail-closed until explicitly designed
        }
        return bool(mapping.get(channel, False))


def _apply_strict(policy: PrivacyPolicy) -> None:
    if not policy.strict_mode:
        return
    # Safe defaults under strict: no plaintext PII/consent; embed off; require URL allowlist for LLM
    policy.allow_public_ip_plaintext = False
    policy.allow_username_plaintext = False
    policy.allow_hostname_plaintext = False
    policy.allow_full_url = False
    policy.allow_consent_plaintext = False
    policy.wecom_allow_host_user = False
    policy.embed_egress_enabled = False


async def _sys_bool(session: AsyncSession | None, key: str, default: bool) -> bool:
    if session is None:
        return default
    from app.services.system_config import get_config_bool

    return await get_config_bool(session, key, default)


async def _sys_value(session: AsyncSession | None, key: str, default: Any) -> Any:
    if session is None:
        return default
    from app.services.system_config import get_config_value

    return await get_config_value(session, key, default)


async def load_privacy_policy(session: AsyncSession | None = None) -> PrivacyPolicy:
    """Load policy with env > strict > system_config > defaults."""
    # Code defaults
    policy = PrivacyPolicy(
        llm_egress_enabled=True,
        ti_egress_enabled=True,
        wecom_egress_enabled=True,
        embed_egress_enabled=False,
        webhook_egress_enabled=True,
        customer_scope_id=(settings.postgres_db or "default"),
    )

    # system_config layer
    policy.strict_mode = await _sys_bool(session, "privacy.strict_mode", False)
    policy.llm_egress_enabled = await _sys_bool(session, "privacy.llm_egress_enabled", True)
    policy.ti_egress_enabled = await _sys_bool(session, "privacy.ti_egress_enabled", True)
    policy.wecom_egress_enabled = await _sys_bool(session, "privacy.wecom_egress_enabled", True)
    policy.embed_egress_enabled = await _sys_bool(session, "privacy.embed_egress_enabled", False)
    policy.webhook_egress_enabled = await _sys_bool(session, "privacy.webhook_egress_enabled", True)
    policy.allow_public_ip_plaintext = await _sys_bool(
        session, "privacy.llm.allow_public_ip_plaintext", False
    )
    policy.allow_username_plaintext = await _sys_bool(
        session, "privacy.llm.allow_username_plaintext", False
    )
    policy.allow_hostname_plaintext = await _sys_bool(
        session, "privacy.llm.allow_hostname_plaintext", False
    )
    policy.allow_full_url = await _sys_bool(session, "privacy.llm.allow_full_url", False)
    policy.wecom_allow_host_user = await _sys_bool(session, "privacy.wecom.allow_host_user", False)

    urls_raw = await _sys_value(session, "privacy.allowed_llm_base_urls", None)
    if isinstance(urls_raw, dict) and "value" in urls_raw:
        urls_raw = urls_raw["value"]
    if isinstance(urls_raw, list):
        policy.allowed_llm_base_urls = [str(u).rstrip("/") for u in urls_raw]
    elif isinstance(urls_raw, str) and urls_raw.strip():
        policy.allowed_llm_base_urls = [u.strip().rstrip("/") for u in urls_raw.split(",") if u.strip()]

    ver = await _sys_value(session, "privacy.policy_version", POLICY_VERSION)
    if isinstance(ver, dict) and "value" in ver:
        ver = ver["value"]
    try:
        policy.policy_version = int(ver)
    except (TypeError, ValueError):
        policy.policy_version = POLICY_VERSION

    # Env force (highest)
    if (v := _env_bool("PRIVACY_STRICT_MODE")) is not None:
        policy.strict_mode = v
    if (v := _env_bool("PRIVACY_LLM_EGRESS_ENABLED")) is not None:
        policy.llm_egress_enabled = v
    if (v := _env_bool("PRIVACY_TI_EGRESS_ENABLED")) is not None:
        policy.ti_egress_enabled = v
    if (v := _env_bool("PRIVACY_WECOM_EGRESS_ENABLED")) is not None:
        policy.wecom_egress_enabled = v
    if (v := _env_bool("PRIVACY_EMBED_EGRESS_ENABLED")) is not None:
        policy.embed_egress_enabled = v
    if (v := _env_bool("PRIVACY_WEBHOOK_EGRESS_ENABLED")) is not None:
        policy.webhook_egress_enabled = v
    if (v := _env_bool("PRIVACY_LLM_ALLOW_PUBLIC_IP_PLAINTEXT")) is not None:
        policy.allow_public_ip_plaintext = v
    if (v := _env_bool("PRIVACY_LLM_ALLOW_USERNAME_PLAINTEXT")) is not None:
        policy.allow_username_plaintext = v
    if (v := _env_bool("PRIVACY_LLM_ALLOW_HOSTNAME_PLAINTEXT")) is not None:
        policy.allow_hostname_plaintext = v
    if (v := _env_bool("PRIVACY_LLM_ALLOW_FULL_URL")) is not None:
        policy.allow_full_url = v
    if (v := _env_bool("PRIVACY_WECOM_ALLOW_HOST_USER")) is not None:
        policy.wecom_allow_host_user = v
    if (urls := _env_list("PRIVACY_ALLOWED_LLM_BASE_URLS")) is not None:
        policy.allowed_llm_base_urls = urls
    scope = os.environ.get("PRIVACY_CUSTOMER_SCOPE_ID")
    if scope and scope.strip():
        policy.customer_scope_id = scope.strip()

    # pydantic Settings (also from env) — explicit bool overrides system_config when set
    if settings.privacy_strict_mode:
        policy.strict_mode = True
    if settings.privacy_llm_egress_enabled is not None:
        policy.llm_egress_enabled = settings.privacy_llm_egress_enabled
    if settings.privacy_ti_egress_enabled is not None:
        policy.ti_egress_enabled = settings.privacy_ti_egress_enabled
    if settings.privacy_wecom_egress_enabled is not None:
        policy.wecom_egress_enabled = settings.privacy_wecom_egress_enabled
    if settings.privacy_embed_egress_enabled is not None:
        policy.embed_egress_enabled = settings.privacy_embed_egress_enabled
    if settings.privacy_webhook_egress_enabled is not None:
        policy.webhook_egress_enabled = settings.privacy_webhook_egress_enabled

    # strict_mode applied last so it can clamp field allow flags
    _apply_strict(policy)

    policy.pseudonym_secret = derive_pseudonym_secret(
        explicit_secret=getattr(settings, "privacy_pseudonym_secret", "") or "",
        jwt_secret=settings.jwt_secret,
        insecure_jwt_default=_INSECURE_JWT,
        app_env=settings.app_env,
    )
    return policy


async def ensure_privacy_config_keys(session: AsyncSession) -> None:
    from app.services.system_config import ensure_config_key

    seeds: list[tuple[str, dict[str, Any], str]] = [
        ("privacy.strict_mode", {"value": False}, "严格隐私模式（禁用明文 PII / embed）"),
        ("privacy.llm_egress_enabled", {"value": True}, "是否允许 LLM 外发（仍需 API Key）"),
        ("privacy.ti_egress_enabled", {"value": True}, "是否允许威胁情报外发（仍需厂商 Key）"),
        ("privacy.wecom_egress_enabled", {"value": True}, "是否允许企业微信协查外发"),
        ("privacy.embed_egress_enabled", {"value": False}, "是否允许 Embedding API 外发"),
        ("privacy.webhook_egress_enabled", {"value": True}, "是否允许 Eval/告警 Webhook 外发"),
        ("privacy.llm.allow_public_ip_plaintext", {"value": False}, "LLM 是否允许公网 IP 明文"),
        ("privacy.llm.allow_username_plaintext", {"value": False}, "LLM 是否允许用户名明文"),
        ("privacy.llm.allow_hostname_plaintext", {"value": False}, "LLM 是否允许主机名明文"),
        ("privacy.llm.allow_full_url", {"value": False}, "LLM 是否允许完整 URL"),
        ("privacy.wecom.allow_host_user", {"value": False}, "WeCom 是否允许主机/用户明文"),
        ("privacy.allowed_llm_base_urls", {"value": []}, "严格模式下允许的 LLM base URL 列表"),
        ("privacy.policy_version", {"value": POLICY_VERSION}, "外发策略版本号"),
    ]
    for key, value, desc in seeds:
        await ensure_config_key(session, key, value, desc)
