"""Aggregation route priority mapping."""

from __future__ import annotations

from app.db.enums import RouteDecision

ROUTE_PRIORITY: dict[RouteDecision, int] = {
    RouteDecision.QUEUE_DEEP_REVIEW: 10,
    RouteDecision.QUEUE_UNCERTAIN: 5,
}


def route_priority(route: RouteDecision) -> int:
    return ROUTE_PRIORITY.get(route, 0)
