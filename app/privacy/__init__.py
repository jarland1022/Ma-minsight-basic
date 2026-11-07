"""P0-06 egress data protection (privacy boundary)."""

from app.privacy.egress_gateway import EgressDeniedError, EgressGateway, get_egress_gateway
from app.privacy.types import EgressChannel

__all__ = [
    "EgressChannel",
    "EgressDeniedError",
    "EgressGateway",
    "get_egress_gateway",
]
