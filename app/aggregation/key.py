"""Event aggregation key computation (Option B)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta, datetime

from app.core.datetime_utils import as_naive_utc


@dataclass(frozen=True)
class AggregationDimensions:
    host_name: str | None
    user_name: str | None
    alert_category: str | None
    window_start: datetime
    host_norm: str
    user_norm: str
    category_norm: str
    event_key: str


def floor_to_window_start(ts: datetime, *, window_hours: int = 24) -> datetime:
    """UTC day boundary when window_hours=24; otherwise fixed-width buckets from epoch."""
    ts = as_naive_utc(ts)

    if window_hours == 24:
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)

    bucket_seconds = window_hours * 3600
    bucket_index = int(ts.replace(tzinfo=UTC).timestamp()) // bucket_seconds
    return datetime.fromtimestamp(bucket_index * bucket_seconds, tz=UTC).replace(tzinfo=None)


def normalize_dimensions(
    *,
    host_name: str | None,
    user_name: str | None,
    alert_category: str | None,
    occurred_at: datetime,
    window_hours: int,
    unknown_host_sentinel: str,
    unknown_user_sentinel: str,
) -> AggregationDimensions:
    window_start = floor_to_window_start(occurred_at, window_hours=window_hours)
    host_norm = (host_name or "").strip().lower() or unknown_host_sentinel
    user_norm = (user_name or "").strip().lower() or unknown_user_sentinel
    category_norm = (alert_category or "uncategorized").strip().lower()

    payload = f"{host_norm}|{user_norm}|{category_norm}|{window_start.isoformat()}"
    event_key = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

    return AggregationDimensions(
        host_name=host_name,
        user_name=user_name,
        alert_category=alert_category,
        window_start=window_start,
        host_norm=host_norm,
        user_norm=user_norm,
        category_norm=category_norm,
        event_key=event_key,
    )
