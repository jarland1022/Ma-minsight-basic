"""P0-08 R2: pipeline STARTED → SUCCESS|FAILED lifecycle (unit)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.audit import AuditResult
from app.services.pipeline_audit import begin_pipeline_audit, finalize_pipeline_audit


@pytest.mark.asyncio
async def test_begin_pipeline_audit_fail_closed_raises_503() -> None:
    session = MagicMock()
    session.rollback = AsyncMock()
    request = MagicMock()
    request.state = SimpleNamespace()
    request.headers = {}
    request.client = SimpleNamespace(host="127.0.0.1")
    auth = SimpleNamespace(user_id=uuid4(), username="admin", client_ip="127.0.0.1")

    with patch(
        "app.services.pipeline_audit.write_audit",
        AsyncMock(side_effect=__import__("app.services.audit", fromlist=["AuditPersistenceError"]).AuditPersistenceError("db")),
    ):
        with pytest.raises(HTTPException) as ei:
            await begin_pipeline_audit(session, request, auth, pipeline="triage")
        assert ei.value.status_code == 503
        assert "not started" in str(ei.value.detail).lower()


@pytest.mark.asyncio
async def test_finalize_success_updates_started_row() -> None:
    audit_id = uuid4()
    row = SimpleNamespace(
        id=audit_id,
        result=AuditResult.STARTED.value,
        detail={"pipeline": "triage", "phase": "started"},
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=row)
    session.commit = AsyncMock()

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.pipeline_audit.db_session.async_session_factory", return_value=cm),
        patch("app.services.pipeline_audit.flag_modified"),
    ):
        ok = await finalize_pipeline_audit(
            audit_id,
            success=True,
            result_detail={"processed": 0},
        )
    assert ok is True
    assert row.result == AuditResult.SUCCESS.value
    assert row.detail["phase"] == "finished"
    assert row.detail["result_summary"]["processed"] == 0
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_finalize_idempotent_when_already_success() -> None:
    audit_id = uuid4()
    row = SimpleNamespace(
        id=audit_id,
        result=AuditResult.SUCCESS.value,
        detail={"pipeline": "triage"},
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=row)
    session.commit = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.pipeline_audit.db_session.async_session_factory", return_value=cm):
        ok = await finalize_pipeline_audit(audit_id, success=False, error="late")
    assert ok is True
    assert row.result == AuditResult.SUCCESS.value  # unchanged
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_finalize_failure_leaves_started_and_returns_false() -> None:
    audit_id = uuid4()
    session = MagicMock()
    session.get = AsyncMock(side_effect=RuntimeError("db down"))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.pipeline_audit.db_session.async_session_factory", return_value=cm):
        ok = await finalize_pipeline_audit(audit_id, success=True)
    assert ok is False
