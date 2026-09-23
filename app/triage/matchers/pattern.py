"""Whitelist match_pattern evaluation."""

from __future__ import annotations

import ipaddress
import re
from typing import Any

from app.triage.schemas.context import AlertSnapshot


def _alert_field_value(alert: AlertSnapshot, field: str) -> Any:
    mapping = {
        "src_ip": alert.src_ip,
        "dst_ip": alert.dst_ip,
        "user_name": alert.user_name,
        "host_name": alert.host_name,
        "rule_id": alert.rule_id,
        "rule_name": alert.rule_name,
        "file_hash": alert.file_hash,
        "alert_category": alert.alert_category,
        "fingerprint": alert.fingerprint,
        "source_alert_id": alert.source_alert_id,
    }
    if field in mapping:
        return mapping[field]
    return alert.normalized_fields.get(field)


def _match_single(alert: AlertSnapshot, condition: dict[str, Any]) -> bool:
    field = condition.get("field")
    if not field:
        return False
    value = _alert_field_value(alert, str(field))
    if value is None:
        return False

    op = condition.get("op", "eq")
    expected = condition.get("value")
    actual = str(value)

    if op == "eq":
        return actual == str(expected)
    if op == "in":
        items = expected if isinstance(expected, list) else [expected]
        return actual in {str(item) for item in items}
    if op == "prefix":
        return actual.startswith(str(expected))
    if op == "regex":
        return bool(re.match(str(expected), actual))
    if op == "in_cidr":
        try:
            return ipaddress.ip_address(actual) in ipaddress.ip_network(str(expected), strict=False)
        except ValueError:
            return False
    return False


def match_pattern(alert: AlertSnapshot, pattern: dict[str, Any]) -> bool:
    if "all" in pattern:
        conditions = pattern.get("all") or []
        return all(_match_single(alert, cond) for cond in conditions)
    if "any" in pattern:
        conditions = pattern.get("any") or []
        return any(_match_single(alert, cond) for cond in conditions)

    field = pattern.get("field")
    if field:
        return _match_single(alert, pattern)

    value = pattern.get("value")
    rule_type = pattern.get("rule_type")
    if rule_type == "ip" and value:
        return alert.src_ip == str(value) or alert.dst_ip == str(value)
    if rule_type == "user" and value:
        return alert.user_name == str(value)
    if rule_type == "host" and value:
        return alert.host_name == str(value)
    if rule_type == "hash" and value:
        return alert.file_hash == str(value)
    return False
