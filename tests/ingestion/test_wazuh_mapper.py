"""Unit tests for Wazuh alert mapping."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.ingestion.adapters.wazuh.mapper import extract_source_alert_id, map_wazuh_alert, parse_occurred_at
from app.ingestion.category import map_wazuh_category
from app.ingestion.severity import map_wazuh_level

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "wazuh"


def load_fixture(name: str) -> dict:
    with (FIXTURES / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def test_map_auth_failed_alert() -> None:
    raw = load_fixture("auth_failed.json")
    source_id = uuid.uuid4()
    alert = map_wazuh_alert(raw, data_source_id=source_id, data_source_name="wazuh")

    assert alert.source_alert_id == "wazuh-alert-auth-failed-001"
    assert alert.rule_id == "5710"
    assert alert.severity == 4
    assert alert.severity_raw == "10"
    assert alert.src_ip == "203.0.113.50"
    assert alert.user_name == "root"
    assert alert.host_name == "web-server-01"
    assert alert.alert_category == "brute_force"
    assert alert.raw_data["_id"] == raw["_id"]
    assert alert.normalized_fields["rule_groups"] == ["authentication_failed", "syslog", "sshd"]


def test_map_syscheck_alert() -> None:
    raw = load_fixture("syscheck_modified.json")
    alert = map_wazuh_alert(raw, data_source_id=uuid.uuid4(), data_source_name="wazuh")

    assert alert.alert_category == "file_integrity"
    assert alert.file_hash == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert alert.host_name == "db-server-01"


def test_map_web_attack_alert() -> None:
    raw = load_fixture("web_attack.json")
    alert = map_wazuh_alert(raw, data_source_id=uuid.uuid4(), data_source_name="wazuh")

    assert alert.alert_category == "web_attack"
    assert alert.severity == 5
    assert alert.dst_ip == "10.0.1.11"
    assert alert.normalized_fields["request_url"] == "/admin/login.php"


def test_severity_mapping_boundaries() -> None:
    assert map_wazuh_level(15) == 5
    assert map_wazuh_level(12) == 5
    assert map_wazuh_level(9) == 4
    assert map_wazuh_level(6) == 3
    assert map_wazuh_level(3) == 2
    assert map_wazuh_level(0) == 1


def test_category_fallback_slug() -> None:
    assert map_wazuh_category(["custom_group"]) == "custom_group"
    assert map_wazuh_category(None) == "uncategorized"


def test_extract_source_alert_id_fallback() -> None:
    raw = {"rule": {"id": "999"}, "timestamp": "2026-06-23T01:00:00Z"}
    assert extract_source_alert_id(raw).startswith("999:")


def test_parse_occurred_at_converts_timezone_to_naive_utc() -> None:
    raw = {"timestamp": "2026-06-25T23:24:35.408+0800"}
    occurred_at = parse_occurred_at(raw)

    assert occurred_at.tzinfo is None
    assert occurred_at.isoformat() == "2026-06-25T15:24:35.408000"
