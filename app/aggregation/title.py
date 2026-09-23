"""Auto-generated event titles."""

from __future__ import annotations


def build_event_title(
    *,
    category: str | None,
    host_name: str | None,
    user_name: str | None,
    alert_count: int,
    max_severity: int,
) -> str:
    category_label = category or "uncategorized"
    host_label = host_name or "unknown-host"
    user_label = user_name or "unknown-user"
    return (
        f"[{category_label}] {host_label} / {user_label} "
        f"({alert_count} alerts, max_severity={max_severity})"
    )
