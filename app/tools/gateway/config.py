"""Tool gateway configuration."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_config import get_config_bool, get_config_int


@dataclass
class ToolGatewayConfig:
    enabled: bool = False
    timeout_seconds: int = 30
    audit_all_calls: bool = True


async def load_tool_gateway_config(session: AsyncSession) -> ToolGatewayConfig:
    return ToolGatewayConfig(
        enabled=await get_config_bool(session, "tools.gateway_enabled", False),
        timeout_seconds=await get_config_int(session, "tools.gateway_timeout_seconds", 30),
        audit_all_calls=await get_config_bool(session, "tools.gateway_audit_all_calls", True),
    )
