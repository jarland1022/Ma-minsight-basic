"""Aggregate regression metrics."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.eval.evaluators.verdict_skills import CaseEvalResult


def compute_regression_metrics(results: list[CaseEvalResult]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    accuracy = passed / total if total else 0.0

    by_verdict: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for r in results:
        exp = r.expected_verdict
        if r.verdict_match:
            by_verdict[exp]["tp"] += 1
        else:
            by_verdict[exp]["fn"] += 1
            if r.actual_verdict:
                by_verdict[r.actual_verdict]["fp"] += 1

    by_verdict_metrics: dict[str, Any] = {}
    for verdict, counts in by_verdict.items():
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        by_verdict_metrics[verdict] = {
            **counts,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
        }

    skill_ok = sum(1 for r in results if r.skills_ok and r.forbidden_ok)
    skill_rate = skill_ok / total if total else 0.0

    return {
        "accuracy": round(accuracy, 4),
        "by_verdict": by_verdict_metrics,
        "skill_compliance_rate": round(skill_rate, 4),
        "total": total,
        "passed": passed,
        "failed": failed,
    }
