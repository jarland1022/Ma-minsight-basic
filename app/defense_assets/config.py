"""Defense asset pipeline configuration."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_config import get_config_bool, get_config_int, get_config_value


@dataclass
class DefenseAssetConfig:
    enabled: bool = True
    poll_interval_minutes: int = 5
    batch_size: int = 20
    auto_close_event: bool = True
    require_disposition_confirm: bool = False
    whitelist_promotion_threshold: int = 3
    whitelist_rule_ttl_days: int = 365
    create_whitelist_on_fp_only: bool = True
    embedding_enabled: bool = False
    embedding_search_enabled: bool = False
    embedding_model: str = "text-embedding-3-small"


async def load_defense_asset_config(session: AsyncSession) -> DefenseAssetConfig:
    model_raw = await get_config_value(session, "defense_assets.embedding_model", "text-embedding-3-small")
    if isinstance(model_raw, dict) and "value" in model_raw:
        embedding_model = str(model_raw["value"])
    elif isinstance(model_raw, str):
        embedding_model = model_raw
    else:
        embedding_model = "text-embedding-3-small"

    return DefenseAssetConfig(
        enabled=await get_config_bool(session, "defense_assets.enabled", True),
        poll_interval_minutes=await get_config_int(session, "defense_assets.poll_interval_minutes", 5),
        batch_size=await get_config_int(session, "defense_assets.batch_size", 20),
        auto_close_event=await get_config_bool(session, "defense_assets.auto_close_event", True),
        require_disposition_confirm=await get_config_bool(
            session, "defense_assets.require_disposition_confirm", False
        ),
        whitelist_promotion_threshold=await get_config_int(
            session, "defense_assets.whitelist_promotion_threshold", 3
        ),
        whitelist_rule_ttl_days=await get_config_int(session, "defense_assets.whitelist_rule_ttl_days", 365),
        create_whitelist_on_fp_only=await get_config_bool(
            session, "defense_assets.create_whitelist_on_fp_only", True
        ),
        embedding_enabled=await get_config_bool(session, "defense_assets.embedding_enabled", False),
        embedding_search_enabled=await get_config_bool(session, "defense_assets.embedding_search_enabled", False),
        embedding_model=embedding_model,
    )


async def ensure_defense_asset_defaults(session: AsyncSession) -> None:
    from app.services.system_config import ensure_config_key

    defaults = [
        ("defense_assets.enabled", {"value": True}, "Enable defense asset sedimentation"),
        ("defense_assets.poll_interval_minutes", {"value": 5}, "Asset pipeline scheduler interval"),
        ("defense_assets.batch_size", {"value": 20}, "Max events settled per run"),
        ("defense_assets.auto_close_event", {"value": True}, "Close event after judgment case written"),
        (
            "defense_assets.require_disposition_confirm",
            {"value": False},
            "Require disposition confirm before closing event",
        ),
        ("defense_assets.whitelist_promotion_threshold", {"value": 3}, "Confirmations to promote whitelist"),
        ("defense_assets.whitelist_rule_ttl_days", {"value": 365}, "Promoted whitelist rule validity days"),
        (
            "defense_assets.create_whitelist_on_fp_only",
            {"value": True},
            "Only create whitelist candidates for false positive verdicts",
        ),
        ("defense_assets.embedding_enabled", {"value": False}, "Compute judgment case embeddings"),
        ("defense_assets.embedding_search_enabled", {"value": False}, "Use embedding search in Agent prompt"),
        ("defense_assets.embedding_model", {"value": "text-embedding-3-small"}, "Embedding model name"),
        ("audit_sample.auto_confirm_whitelist", {"value": False}, "Audit sample FP auto-confirms whitelist"),
    ]
    for key, value, description in defaults:
        await ensure_config_key(session, key, value, description)
