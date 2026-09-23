"""UTC datetime helpers for naive PostgreSQL TIMESTAMP columns."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return current UTC as naive datetime for TIMESTAMP WITHOUT TIME ZONE."""
    return datetime.now(UTC).replace(tzinfo=None)


def as_naive_utc(value: datetime) -> datetime:
    """Convert aware or naive datetime to naive UTC."""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def hours_ago(hours: float) -> datetime:
    """Naive UTC timestamp N hours before now (safe for DB comparisons)."""
    from datetime import timedelta

    return utc_now() - timedelta(hours=hours)
