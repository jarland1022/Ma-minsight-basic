"""Alert fingerprint for dedup (used by triage in phase 3)."""

from __future__ import annotations

import hashlib


def compute_fingerprint(
    *,
    data_source_name: str,
    rule_id: str | None,
    src_ip: str | None,
    dst_ip: str | None,
    user_name: str | None,
    host_name: str | None,
    alert_category: str | None,
) -> str:
    """Stable fingerprint without occurred_at — same pattern merges in time window."""
    parts = [
        data_source_name,
        rule_id or "",
        src_ip or "",
        dst_ip or "",
        user_name or "",
        host_name or "",
        alert_category or "",
    ]
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
