"""Unified external tool invocation facade for Skills."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import ActorType
from app.models.system import AuditLog
from app.tools.gateway.adapters.registry import get_adapter
from app.tools.gateway.config import ToolGatewayConfig, load_tool_gateway_config

logger = logging.getLogger(__name__)


class ToolGatewayDisabledError(RuntimeError):
    pass


@dataclass
class GatewayCallResult:
    adapter: str
    operation: str
    data: dict[str, Any]
    latency_ms: int


class ToolGatewayClient:
    def __init__(self, config: ToolGatewayConfig | None = None) -> None:
        self._config = config

    async def invoke(
        self,
        session: AsyncSession,
        *,
        adapter: str,
        operation: str,
        params: dict[str, Any] | None = None,
    ) -> GatewayCallResult:
        config = self._config or await load_tool_gateway_config(session)
        if not config.enabled:
            raise ToolGatewayDisabledError("tools.gateway_enabled is false")

        impl = get_adapter(adapter)
        start = time.perf_counter()
        data = await impl.invoke(
            operation,
            params or {},
            session=session,
            timeout_seconds=config.timeout_seconds,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        if config.audit_all_calls:
            session.add(
                AuditLog(
                    actor_type=ActorType.SYSTEM,
                    action="tools.gateway.call",
                    resource_type="tool_gateway",
                    resource_id=f"{adapter}:{operation}",
                    detail={
                        "adapter": adapter,
                        "operation": operation,
                        "latency_ms": latency_ms,
                        "params_keys": sorted((params or {}).keys()),
                    },
                )
            )

        return GatewayCallResult(
            adapter=adapter,
            operation=operation,
            data=data,
            latency_ms=latency_ms,
        )

    @staticmethod
    async def invoke_optional(
        session: AsyncSession,
        *,
        adapter: str,
        operation: str,
        params: dict[str, Any] | None = None,
    ) -> GatewayCallResult | None:
        """Call gateway when enabled; return None when disabled (Skills stay backward compatible)."""
        config = await load_tool_gateway_config(session)
        if not config.enabled:
            return None
        return await ToolGatewayClient(config).invoke(
            session,
            adapter=adapter,
            operation=operation,
            params=params,
        )
