"""Severity component for rule scoring."""

from __future__ import annotations

SEVERITY_TO_SCORE = {
    1: 20.0,
    2: 40.0,
    3: 60.0,
    4: 80.0,
    5: 100.0,
}


def severity_score(severity: int) -> float:
    return SEVERITY_TO_SCORE.get(severity, 60.0)
