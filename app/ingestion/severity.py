"""Severity normalization across alert sources."""

from __future__ import annotations


def map_wazuh_level(level: int | str | None) -> int:
    """Map Wazuh rule.level (0-15) to standardized severity 1-5."""
    if level is None:
        return 3
    try:
        value = int(level)
    except (TypeError, ValueError):
        return 3

    if value >= 12:
        return 5
    if value >= 9:
        return 4
    if value >= 6:
        return 3
    if value >= 3:
        return 2
    return 1
