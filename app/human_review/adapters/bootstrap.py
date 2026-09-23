"""Register IM channel adapters."""

from __future__ import annotations

from app.human_review.adapters.mock.adapter import MockImAdapter
from app.human_review.adapters.registry import ImAdapterRegistry
from app.human_review.adapters.wecom.adapter import WeComAdapter

ImAdapterRegistry.register("mock", MockImAdapter)
ImAdapterRegistry.register("wecom", WeComAdapter)
