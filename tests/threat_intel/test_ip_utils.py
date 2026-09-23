"""Tests for threat intel IP helpers."""

from app.threat_intel.ip_utils import is_public_ip, normalize_ip


def test_normalize_ip() -> None:
    assert normalize_ip(" 203.0.113.1 ") == "203.0.113.1"
    assert normalize_ip("invalid") is None


def test_is_public_ip() -> None:
    assert is_public_ip("203.0.113.1") is True
    assert is_public_ip("172.18.131.88") is False
    assert is_public_ip("10.0.0.1") is False
    assert is_public_ip("183.6.90.91") is True
