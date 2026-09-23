"""Event title and priority tests."""

from app.aggregation.priority import route_priority
from app.aggregation.title import build_event_title
from app.db.enums import RouteDecision


def test_build_event_title() -> None:
    title = build_event_title(
        category="brute_force",
        host_name="web-01",
        user_name="root",
        alert_count=3,
        max_severity=4,
    )
    assert "[brute_force]" in title
    assert "3 alerts" in title
    assert "max_severity=4" in title


def test_route_priority_deep_over_uncertain() -> None:
    assert route_priority(RouteDecision.QUEUE_DEEP_REVIEW) > route_priority(
        RouteDecision.QUEUE_UNCERTAIN
    )
