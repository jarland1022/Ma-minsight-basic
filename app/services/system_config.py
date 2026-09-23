"""System configuration helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system import SystemConfig


async def get_config_value(session: AsyncSession, key: str, default: Any = None) -> Any:
    result = await session.execute(select(SystemConfig).where(SystemConfig.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        return default
    return row.value


async def get_config_int(session: AsyncSession, key: str, default: int) -> int:
    value = await get_config_value(session, key, default)
    if isinstance(value, dict) and "value" in value:
        return int(value["value"])
    if isinstance(value, int):
        return value
    return default


async def get_config_float(session: AsyncSession, key: str, default: float) -> float:
    value = await get_config_value(session, key, default)
    if isinstance(value, dict) and "value" in value:
        return float(value["value"])
    if isinstance(value, (int, float)):
        return float(value)
    return default


async def get_config_bool(session: AsyncSession, key: str, default: bool) -> bool:
    value = await get_config_value(session, key, default)
    if isinstance(value, dict) and "value" in value:
        return bool(value["value"])
    if isinstance(value, bool):
        return value
    return default


async def ensure_config_key(
    session: AsyncSession,
    key: str,
    value: dict[str, Any],
    description: str | None = None,
) -> None:
    """Insert default config only when missing; never overwrite operator edits."""
    result = await session.execute(select(SystemConfig).where(SystemConfig.key == key))
    existing = result.scalar_one_or_none()
    if existing is None:
        session.add(SystemConfig(key=key, value=value, description=description))
    elif description and not existing.description:
        existing.description = description
