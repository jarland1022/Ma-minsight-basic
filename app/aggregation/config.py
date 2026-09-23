"""Event aggregation configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_config import get_config_int, get_config_value

DEFAULT_UNKNOWN_HOST = "__unknown_host__"
DEFAULT_UNKNOWN_USER = "__unknown_user__"


@dataclass
class AggregationConfig:
    window_hours: int = 24
    batch_size: int = 500
    unknown_host_sentinel: str = DEFAULT_UNKNOWN_HOST
    unknown_user_sentinel: str = DEFAULT_UNKNOWN_USER


async def load_aggregation_config(session: AsyncSession) -> AggregationConfig:
    host_sentinel = await get_config_value(session, "event.unknown_host_sentinel", DEFAULT_UNKNOWN_HOST)
    user_sentinel = await get_config_value(session, "event.unknown_user_sentinel", DEFAULT_UNKNOWN_USER)

    def _unwrap(value: Any, default: str) -> str:
        if isinstance(value, dict) and "value" in value:
            return str(value["value"])
        if isinstance(value, str):
            return value
        return default

    return AggregationConfig(
        window_hours=await get_config_int(session, "event.aggregation_window_hours", 24),
        batch_size=await get_config_int(session, "event.aggregation_batch_size", 500),
        unknown_host_sentinel=_unwrap(host_sentinel, DEFAULT_UNKNOWN_HOST),
        unknown_user_sentinel=_unwrap(user_sentinel, DEFAULT_UNKNOWN_USER),
    )


async def ensure_aggregation_defaults(session: AsyncSession) -> None:
    from app.services.system_config import ensure_config_key

    defaults: list[tuple[str, dict, str]] = [
        ("event.aggregation_window_hours", {"value": 24}, "UTC-aligned aggregation window hours"),
        ("event.aggregation_batch_size", {"value": 500}, "Max alerts aggregated per run"),
        ("event.aggregation_poll_interval_minutes", {"value": 2}, "Aggregation scheduler interval"),
        ("event.unknown_host_sentinel", {"value": DEFAULT_UNKNOWN_HOST}, "Sentinel when host_name missing"),
        ("event.unknown_user_sentinel", {"value": DEFAULT_UNKNOWN_USER}, "Sentinel when user_name missing"),
    ]
    for key, value, description in defaults:
        await ensure_config_key(session, key, value, description)
