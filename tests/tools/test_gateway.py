"""Tool gateway client tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.gateway.client import ToolGatewayClient, ToolGatewayDisabledError
from app.tools.gateway.config import ToolGatewayConfig


@pytest.mark.asyncio
async def test_gateway_disabled_raises() -> None:
    session = AsyncMock()
    client = ToolGatewayClient(ToolGatewayConfig(enabled=False))
    with pytest.raises(ToolGatewayDisabledError):
        await client.invoke(session, adapter="cmdb", operation="lookup_host", params={"host_name": "x"})


@pytest.mark.asyncio
async def test_gateway_invoke_optional_returns_none_when_disabled() -> None:
    session = AsyncMock()
    with patch(
        "app.tools.gateway.client.load_tool_gateway_config",
        AsyncMock(return_value=ToolGatewayConfig(enabled=False)),
    ):
        result = await ToolGatewayClient.invoke_optional(
            session,
            adapter="cmdb",
            operation="lookup_host",
            params={"host_name": "web-01"},
        )
    assert result is None


@pytest.mark.asyncio
async def test_gateway_invoke_cmdb_mock() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    client = ToolGatewayClient(ToolGatewayConfig(enabled=True, audit_all_calls=True))
    result = await client.invoke(
        session,
        adapter="cmdb",
        operation="lookup_host",
        params={"host_name": "web-server-01"},
    )
    assert result.data["mode"] == "mock"
    assert result.data["host_name"] == "web-server-01"
    session.add.assert_called_once()
