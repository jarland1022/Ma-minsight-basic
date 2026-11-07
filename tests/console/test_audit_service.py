"""P0-08 audit service: fail-closed vs soft, high-risk classification."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.audit import (
    AuditPersistenceError,
    AuditResult,
    is_high_risk_action,
    write_audit,
)
from app.services.audit_redact import redact_for_audit


def test_high_risk_classification() -> None:
    assert is_high_risk_action("config.update")
    assert is_high_risk_action("disposition.confirm")
    assert is_high_risk_action("whitelist.candidate.confirm")
    assert is_high_risk_action("data.export")
    assert is_high_risk_action("auth.change_password")
    assert not is_high_risk_action("pipeline.manual_run")
    assert not is_high_risk_action("http.post")
    assert not is_high_risk_action("auth.login")


@pytest.mark.asyncio
async def test_write_audit_redacts_detail_before_persist() -> None:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    row = await write_audit(
        session,
        action="config.update",
        actor_id="admin",
        resource_type="system_config",
        resource_id="llm",
        detail={"note": "ok"},
        before={"value": {"api_key": "sk-before", "n": 1}},
        after={"value": {"api_key": "sk-after", "n": 2}},
        result=AuditResult.SUCCESS,
        correlation_id="cid-1",
        client_ip="127.0.0.1",
        commit=False,
        fail_closed=True,
    )
    assert row is not None
    assert row.detail["before"]["value"]["api_key"] == "***REDACTED***"
    assert row.detail["after"]["value"]["n"] == 2
    assert row.result == "success"
    assert row.correlation_id == "cid-1"
    assert row.client_ip == "127.0.0.1"
    session.add.assert_called_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_fail_closed_raises_on_flush_error() -> None:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock(side_effect=RuntimeError("db down"))

    with pytest.raises(AuditPersistenceError, match="config.update"):
        await write_audit(
            session,
            action="config.update",
            detail={"x": 1},
            commit=False,
            fail_closed=True,
        )


@pytest.mark.asyncio
async def test_soft_fail_returns_none() -> None:
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock(side_effect=RuntimeError("db down"))

    row = await write_audit(
        session,
        action="http.post",
        detail={"status_code": 200},
        commit=True,
        fail_closed=False,
    )
    assert row is None


def test_redact_does_not_mutate_original() -> None:
    original = {"password": "secret", "ok": 1}
    copy_like = redact_for_audit(original)
    assert original["password"] == "secret"
    assert copy_like["password"] == "***REDACTED***"
