"""Adapter type registry."""

from __future__ import annotations

from typing import Type

from app.ingestion.adapters.base import AlertSourceAdapter


class AdapterRegistry:
    _adapters: dict[str, Type[AlertSourceAdapter]] = {}

    @classmethod
    def register(cls, adapter_type: str, adapter_cls: Type[AlertSourceAdapter]) -> None:
        cls._adapters[adapter_type] = adapter_cls

    @classmethod
    def get(cls, adapter_type: str) -> Type[AlertSourceAdapter]:
        if adapter_type not in cls._adapters:
            known = ", ".join(sorted(cls._adapters)) or "(none)"
            raise KeyError(f"Unknown adapter_type '{adapter_type}'. Registered: {known}")
        return cls._adapters[adapter_type]

    @classmethod
    def create(cls, adapter_type: str) -> AlertSourceAdapter:
        return cls.get(adapter_type)()

    @classmethod
    def registered_types(cls) -> list[str]:
        return sorted(cls._adapters)
