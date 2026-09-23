"""Event key computation tests."""

from __future__ import annotations

from datetime import UTC, datetime

from app.aggregation.config import DEFAULT_UNKNOWN_HOST, DEFAULT_UNKNOWN_USER
from app.aggregation.key import floor_to_window_start, normalize_dimensions


def test_floor_to_window_start_utc_midnight() -> None:
    ts = datetime(2026, 6, 23, 15, 30, tzinfo=UTC)
    start = floor_to_window_start(ts, window_hours=24)
    assert start == datetime(2026, 6, 23, 0, 0, tzinfo=UTC)


def test_same_key_for_same_dimensions() -> None:
    ts = datetime(2026, 6, 23, 10, 0, tzinfo=UTC)
    a = normalize_dimensions(
        host_name="Web-Server-01",
        user_name="root",
        alert_category="brute_force",
        occurred_at=ts,
        window_hours=24,
        unknown_host_sentinel=DEFAULT_UNKNOWN_HOST,
        unknown_user_sentinel=DEFAULT_UNKNOWN_USER,
    )
    b = normalize_dimensions(
        host_name="web-server-01",
        user_name="root",
        alert_category="brute_force",
        occurred_at=datetime(2026, 6, 23, 18, 0, tzinfo=UTC),
        window_hours=24,
        unknown_host_sentinel=DEFAULT_UNKNOWN_HOST,
        unknown_user_sentinel=DEFAULT_UNKNOWN_USER,
    )
    assert a.event_key == b.event_key


def test_different_day_different_key() -> None:
    common = dict(
        host_name="host1",
        user_name="user1",
        alert_category="brute_force",
        window_hours=24,
        unknown_host_sentinel=DEFAULT_UNKNOWN_HOST,
        unknown_user_sentinel=DEFAULT_UNKNOWN_USER,
    )
    a = normalize_dimensions(occurred_at=datetime(2026, 6, 23, 10, 0, tzinfo=UTC), **common)
    b = normalize_dimensions(occurred_at=datetime(2026, 6, 24, 10, 0, tzinfo=UTC), **common)
    assert a.event_key != b.event_key


def test_sentinel_for_missing_host_user() -> None:
    dims = normalize_dimensions(
        host_name=None,
        user_name=None,
        alert_category=None,
        occurred_at=datetime(2026, 6, 23, 1, 0, tzinfo=UTC),
        window_hours=24,
        unknown_host_sentinel=DEFAULT_UNKNOWN_HOST,
        unknown_user_sentinel=DEFAULT_UNKNOWN_USER,
    )
    assert dims.host_norm == DEFAULT_UNKNOWN_HOST
    assert dims.user_norm == DEFAULT_UNKNOWN_USER
    assert dims.category_norm == "uncategorized"
