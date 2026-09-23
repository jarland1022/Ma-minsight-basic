"""Default category risk weights for triage rule scoring."""

from __future__ import annotations

DEFAULT_CATEGORY_RISK: dict[str, float] = {
    "brute_force": 90.0,
    "malware": 95.0,
    "web_attack": 85.0,
    "network_intrusion": 88.0,
    "file_integrity": 70.0,
    "login_anomaly": 75.0,
    "authentication": 60.0,
    "firewall": 55.0,
    "windows_event": 50.0,
    "host_anomaly": 65.0,
    "syslog": 40.0,
    "compliance": 35.0,
    "data_exfiltration": 92.0,
    "privilege_escalation": 93.0,
    "uncategorized": 50.0,
}


def category_risk_score(category: str | None, weights: dict[str, float]) -> float:
    if not category:
        return weights.get("uncategorized", 50.0)
    return weights.get(category, weights.get("uncategorized", 50.0))
