"""Disposition simulation configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_config import get_config_bool, get_config_value


@dataclass
class DispositionConfig:
    simulation_enabled: bool = False
    require_approval: bool = True
    allowed_action_types: list[str] = field(
        default_factory=lambda: ["block_ip", "isolate_host", "disable_user"]
    )
    mock_mode: bool = True


async def load_disposition_config(session: AsyncSession) -> DispositionConfig:
    allowed_raw = await get_config_value(
        session,
        "disposition.allowed_action_types",
        ["block_ip", "isolate_host", "disable_user"],
    )
    if isinstance(allowed_raw, dict) and "value" in allowed_raw:
        allowed = [str(v) for v in allowed_raw["value"]]
    elif isinstance(allowed_raw, list):
        allowed = [str(v) for v in allowed_raw]
    else:
        allowed = ["block_ip", "isolate_host", "disable_user"]

    mock_env = os.getenv("DISPOSITION_MOCK_MODE", "true").lower()
    mock_mode = mock_env not in {"0", "false", "no"}

    return DispositionConfig(
        simulation_enabled=await get_config_bool(session, "disposition.simulation_enabled", False),
        require_approval=await get_config_bool(session, "disposition.require_approval", True),
        allowed_action_types=allowed,
        mock_mode=mock_mode,
    )
