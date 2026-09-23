"""Ensure threat intel skill uses naive UTC for DB comparisons."""

from datetime import UTC, datetime

from app.core.datetime_utils import as_naive_utc, utc_now


def test_utc_now_is_naive() -> None:
    now = utc_now()
    assert now.tzinfo is None


def test_utc_now_matches_postgres_timestamp_expectation() -> None:
    aware = datetime.now(UTC)
    naive = utc_now()
    assert naive <= aware.replace(tzinfo=None)


def test_as_naive_utc_strips_timezone() -> None:
    aware = datetime.now(UTC)
    assert as_naive_utc(aware).tzinfo is None
