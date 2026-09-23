"""Pattern matcher tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.triage.matchers.pattern import match_pattern
from app.triage.schemas.context import AlertSnapshot


def _alert(**kwargs) -> AlertSnapshot:
    base = dict(
        id=uuid.uuid4(),
        data_source_id=uuid.uuid4(),
        data_source_name="wazuh",
        source_alert_id="1",
        fingerprint="abc",
        severity=3,
        occurred_at=datetime.now(UTC),
    )
    base.update(kwargs)
    return AlertSnapshot(**base)


def test_eq_match() -> None:
    alert = _alert(src_ip="10.0.0.5")
    assert match_pattern(alert, {"field": "src_ip", "op": "eq", "value": "10.0.0.5"})


def test_in_cidr_match() -> None:
    alert = _alert(src_ip="10.0.0.42")
    assert match_pattern(alert, {"field": "src_ip", "op": "in_cidr", "value": "10.0.0.0/24"})


def test_composite_all_match() -> None:
    alert = _alert(rule_id="5710", src_ip="10.0.0.5")
    pattern = {
        "all": [
            {"field": "rule_id", "op": "eq", "value": "5710"},
            {"field": "src_ip", "op": "in_cidr", "value": "10.0.0.0/24"},
        ]
    }
    assert match_pattern(alert, pattern)


def test_composite_all_fail() -> None:
    alert = _alert(rule_id="5710", src_ip="203.0.113.1")
    pattern = {
        "all": [
            {"field": "rule_id", "op": "eq", "value": "5710"},
            {"field": "src_ip", "op": "eq", "value": "10.0.0.5"},
        ]
    }
    assert not match_pattern(alert, pattern)
