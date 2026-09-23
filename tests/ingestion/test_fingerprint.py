"""Tests for alert fingerprint computation."""

from app.ingestion.fingerprint import compute_fingerprint


def test_fingerprint_stable_for_same_inputs() -> None:
    kwargs = dict(
        data_source_name="wazuh",
        rule_id="5710",
        src_ip="1.2.3.4",
        dst_ip=None,
        user_name="root",
        host_name="host1",
        alert_category="brute_force",
    )
    assert compute_fingerprint(**kwargs) == compute_fingerprint(**kwargs)


def test_fingerprint_changes_with_entity() -> None:
    base = dict(
        data_source_name="wazuh",
        rule_id="5710",
        src_ip="1.2.3.4",
        dst_ip=None,
        user_name="root",
        host_name="host1",
        alert_category="brute_force",
    )
    a = compute_fingerprint(**base)
    b = compute_fingerprint(**{**base, "src_ip": "5.6.7.8"})
    assert a != b
