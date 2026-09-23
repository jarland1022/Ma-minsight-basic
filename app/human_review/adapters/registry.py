"""IM adapter registry."""

from __future__ import annotations

from typing import Type

from app.db.enums import ImChannel
from app.human_review.adapters.base import ImChannelAdapter


class ImAdapterRegistry:
    _adapters: dict[str, Type[ImChannelAdapter]] = {}

    @classmethod
    def register(cls, channel: str, adapter_cls: Type[ImChannelAdapter]) -> None:
        cls._adapters[channel] = adapter_cls

    @classmethod
    def create(cls, channel: str) -> ImChannelAdapter:
        if channel not in cls._adapters:
            known = ", ".join(sorted(cls._adapters)) or "(none)"
            raise KeyError(f"Unknown IM channel '{channel}'. Registered: {known}")
        return cls._adapters[channel]()

    @classmethod
    def registered_channels(cls) -> list[str]:
        return sorted(cls._adapters)
