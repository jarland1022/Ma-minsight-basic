"""Incremental pull cursor and batch result models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.datetime_utils import as_naive_utc


class CursorState(BaseModel):
    version: int = 1
    mode: str = "search_after"
    last_occurred_at: datetime | None = None
    last_sort_values: list[Any] | None = None
    last_successful_run_at: datetime | None = None
    total_ingested: int = 0

    @field_validator("last_occurred_at", "last_successful_run_at", mode="before")
    @classmethod
    def _normalize_cursor_datetimes(cls, value: object) -> datetime | None:
        if value is None or not isinstance(value, datetime):
            return value
        return as_naive_utc(value)


class PullStats(BaseModel):
    fetched: int = 0
    map_errors: int = 0


class PullResult(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    next_cursor: CursorState
    has_more: bool = False
    stats: PullStats = Field(default_factory=PullStats)
