"""Compare health-check actual state vs expected_outcome."""

from __future__ import annotations

from typing import Any


def diff_outcome(expected: dict[str, Any], actual: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    mismatches: dict[str, Any] = {}
    for key, exp_val in expected.items():
        act_val = actual.get(key)
        if act_val != exp_val:
            mismatches[key] = {"expected": exp_val, "actual": act_val}
    passed = len(mismatches) == 0
    return passed, mismatches
