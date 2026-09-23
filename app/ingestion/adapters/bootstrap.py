"""Register all built-in adapters on import."""

from app.ingestion.adapters import health_probe  # noqa: F401
from app.ingestion.adapters import mock  # noqa: F401
from app.ingestion.adapters import wazuh  # noqa: F401
from app.ingestion.adapters.registry import AdapterRegistry

__all__ = ["AdapterRegistry"]
