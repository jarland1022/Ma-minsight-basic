"""P0-08 sensitive field redaction tests."""

from app.services.audit_redact import redact_for_audit, redact_string


def test_redacts_password_keys() -> None:
    payload = {
        "username": "admin",
        "password": "changeme",
        "nested": {"api_key": "sk-secret", "threshold": 3},
        "safe": "ok",
    }
    out = redact_for_audit(payload)
    assert out["username"] == "admin"
    assert out["password"] == "***REDACTED***"
    assert out["nested"]["api_key"] == "***REDACTED***"
    assert out["nested"]["threshold"] == 3
    assert out["safe"] == "ok"


def test_redacts_token_and_secret_variants() -> None:
    payload = {
        "access_token": "eyJhbGciOi...",
        "mfa_secret": "JBSWY3DPEHPK3PXP",
        "jwt_secret": "super-secret",
        "Authorization": "Bearer abc.def",
        "deepseek_api_key": "sk-xxx",
        "client_secret": "cs",
    }
    out = redact_for_audit(payload)
    for key in payload:
        assert out[key] == "***REDACTED***", key


def test_redacts_bearer_in_strings() -> None:
    assert "abc.def" not in redact_string("Authorization: Bearer abc.def.ghi")
    assert "***REDACTED***" in redact_string("Authorization: Bearer abc.def.ghi")


def test_redacts_inline_key_value() -> None:
    text = "api_key=sk-live-12345 password: hunter2"
    out = redact_string(text)
    assert "sk-live-12345" not in out
    assert "hunter2" not in out


def test_before_after_config_shape() -> None:
    before = {"value": {"llm_api_key": "sk-old", "batch_size": 10}}
    after = {"value": {"llm_api_key": "sk-new", "batch_size": 20}}
    safe_before = redact_for_audit(before)
    safe_after = redact_for_audit(after)
    assert safe_before["value"]["llm_api_key"] == "***REDACTED***"
    assert safe_after["value"]["batch_size"] == 20
    assert safe_after["value"]["llm_api_key"] == "***REDACTED***"


def test_list_and_tuple_redaction() -> None:
    assert redact_for_audit([{"token": "x"}, "ok"])[0]["token"] == "***REDACTED***"
    assert redact_for_audit(({"secret": "y"},))[0]["secret"] == "***REDACTED***"
