"""Mock CMDB adapter for tool gateway skeleton."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.gateway.adapters.base import ToolGatewayAdapter


class CmdbAdapter(ToolGatewayAdapter):
    name = "cmdb"

    async def invoke(
        self,
        operation: str,
        params: dict[str, Any],
        *,
        session: AsyncSession | None = None,
        timeout_seconds: int = 30,
    ) -> dict[str, Any]:
        if operation == "lookup_host":
            host = str(params.get("host_name") or params.get("host") or "").strip()
            return {
                "adapter": self.name,
                "operation": operation,
                "mode": "mock",
                "host_name": host,
                "owner_team": "unknown",
                "business_systems": [],
                "note": "CMDB gateway mock — set CMDB_API_URL for real integration",
            }
        if operation == "lookup_ip":
            ip = str(params.get("ip") or "").strip()
            return {
                "adapter": self.name,
                "operation": operation,
                "mode": "mock",
                "ip": ip,
                "asset_type": "server",
            }
        raise ValueError(f"unsupported cmdb operation: {operation}")
