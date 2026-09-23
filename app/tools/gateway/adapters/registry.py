"""Adapter registry for tool gateway."""

from __future__ import annotations

from app.tools.gateway.adapters.base import ToolGatewayAdapter
from app.tools.gateway.adapters.cmdb import CmdbAdapter

_ADAPTERS: dict[str, ToolGatewayAdapter] = {
    CmdbAdapter.name: CmdbAdapter(),
}


def get_adapter(name: str) -> ToolGatewayAdapter:
    adapter = _ADAPTERS.get(name.lower().strip())
    if adapter is None:
        raise KeyError(f"unknown tool gateway adapter: {name}")
    return adapter


def list_adapters() -> list[str]:
    return sorted(_ADAPTERS.keys())
