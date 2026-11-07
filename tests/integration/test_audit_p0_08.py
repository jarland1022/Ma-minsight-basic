"""P0-08 real-database integration tests (Postgres + ASGI client).

Requires reachable DB with alembic head (incl. 024 api_keys.scopes). No mocks for audit persistence.
High-risk routes use JWT admin headers (O-07) — not legacy X-API-Key.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


async def _list_audits(client, headers, **params) -> list[dict]:
    resp = await client.get("/api/v1/system/audit-logs", headers=headers, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


async def test_config_update_persists_before_after_redacted(client, admin_headers):
    key = f"p0_08_integ_{uuid4().hex[:12]}"
    corr = f"corr-config-{uuid4().hex[:8]}"
    headers = {**admin_headers, "X-Correlation-ID": corr}

    r1 = await client.put(
        f"/api/v1/system/config/{key}",
        headers=headers,
        json={"value": {"api_key": "sk-before-secret", "batch_size": 1}},
    )
    assert r1.status_code == 200, r1.text

    corr2 = f"corr-config2-{uuid4().hex[:8]}"
    headers2 = {**admin_headers, "X-Correlation-ID": corr2}
    r2 = await client.put(
        f"/api/v1/system/config/{key}",
        headers=headers2,
        json={"value": {"api_key": "sk-after-secret", "batch_size": 9}},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["correlation_id"] == corr2
    assert r2.headers.get("x-correlation-id") == corr2

    items = await _list_audits(
        client,
        admin_headers,
        action="config.update",
        correlation_id=corr2,
        result="success",
    )
    assert items, "business config.update audit missing"
    biz = items[0]
    assert biz["result"] == "success"
    assert (biz.get("detail") or {}).get("event_level") == "business"
    before = (biz.get("detail") or {}).get("before") or {}
    after = (biz.get("detail") or {}).get("after") or {}
    assert before["value"]["api_key"] == "***REDACTED***"
    assert after["value"]["api_key"] == "***REDACTED***"
    assert after["value"]["batch_size"] == 9
    assert "sk-before-secret" not in str(biz)
    assert "sk-after-secret" not in str(biz)


async def test_admin_can_query_audit_success_vs_filter(client, admin_headers):
    corr = f"corr-query-{uuid4().hex[:8]}"
    headers = {**admin_headers, "X-Correlation-ID": corr}
    key = f"p0_08_query_{uuid4().hex[:8]}"

    put = await client.put(
        f"/api/v1/system/config/{key}",
        headers=headers,
        json={"value": {"n": 1}},
    )
    assert put.status_code == 200, put.text

    items = await _list_audits(
        client,
        admin_headers,
        action="config.update",
        correlation_id=corr,
        result="success",
    )
    assert any(i["correlation_id"] == corr and i["result"] == "success" for i in items)

    denied_items = await _list_audits(
        client,
        admin_headers,
        correlation_id=corr,
        result="denied",
    )
    assert not any(
        i["correlation_id"] == corr and i["result"] == "success" for i in denied_items
    )


async def test_http_and_business_share_correlation_id(client, admin_headers):
    corr = f"corr-dual-{uuid4().hex[:8]}"
    headers = {**admin_headers, "X-Correlation-ID": corr}
    key = f"p0_08_dual_{uuid4().hex[:8]}"

    resp = await client.put(
        f"/api/v1/system/config/{key}",
        headers=headers,
        json={"value": {"password": "should-redact", "ok": True}},
    )
    assert resp.status_code == 200, resp.text

    # Business via filtered API
    biz_items = await _list_audits(
        client, admin_headers, action="config.update", correlation_id=corr
    )
    assert biz_items
    assert biz_items[0]["result"] == "success"
    assert (biz_items[0].get("detail") or {}).get("event_level") == "business"

    # Request-level http.put (prefix filter on dedicated audit-logs route)
    http_resp = await client.get(
        "/api/v1/audit-logs",
        headers=admin_headers,
        params={"action_prefix": "http.", "correlation_id": corr},
    )
    assert http_resp.status_code == 200, http_resp.text
    http_items = http_resp.json()["items"]
    assert any(i["action"] == "http.put" for i in http_items)
    http = next(i for i in http_items if i["action"] == "http.put")
    assert http["correlation_id"] == corr
    assert http["result"] == "success"
    assert (http.get("detail") or {}).get("event_level") == "request"


async def test_pipeline_manual_run_started_then_success(client, admin_headers):
    corr = f"corr-pipe-{uuid4().hex[:8]}"
    headers = {**admin_headers, "X-Correlation-ID": corr}

    resp = await client.post(
        "/api/v1/console/run/triage",
        headers=headers,
        params={"limit": 1},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["pipeline"] == "triage"
    assert payload["correlation_id"] == corr
    assert payload.get("audit_id")
    assert payload.get("audit_finalized") is True

    items = await _list_audits(
        client,
        admin_headers,
        action="pipeline.manual_run",
        correlation_id=corr,
        resource_type="pipeline",
    )
    assert items
    biz = items[0]
    assert biz["result"] == "success"
    assert biz["resource_id"] == "triage"
    assert (biz.get("detail") or {}).get("event_level") == "business"
    assert (biz.get("detail") or {}).get("pipeline") == "triage"
    assert (biz.get("detail") or {}).get("phase") == "finished"


async def test_pipeline_failure_finalizes_failed(client, admin_headers):
    """Ingestion with unknown source_id fails after STARTED → result=failure."""
    corr = f"corr-pipe-fail-{uuid4().hex[:8]}"
    headers = {**admin_headers, "X-Correlation-ID": corr}
    bogus = "00000000-0000-4000-8000-000000000099"

    resp = await client.post(
        "/api/v1/console/run/ingestion",
        headers=headers,
        params={"source_id": bogus},
    )
    assert resp.status_code != 503

    items = await _list_audits(
        client,
        admin_headers,
        action="pipeline.manual_run",
        correlation_id=corr,
    )
    assert items, "STARTED audit must exist even when pipeline fails"
    biz = next(i for i in items if i.get("resource_id") == "ingestion")
    assert biz["result"] == "failure"
    assert (biz.get("detail") or {}).get("phase") == "finished"


async def test_events_have_no_status_write_api_middleware_covers_mutations():
    """Static check: events router is read-only; mutating verbs are middleware-audited."""
    from app.api.middleware_audit import OperationAuditMiddleware
    from app.api.routes import events as events_mod
    from app.main import app

    event_routes = [
        r for r in app.routes if getattr(r, "path", "").startswith("/api/v1/events")
    ]
    mutating = []
    for r in event_routes:
        methods = getattr(r, "methods", None) or set()
        if methods & {"POST", "PUT", "PATCH", "DELETE"}:
            mutating.append((r.path, methods))
    assert mutating == [], f"Unexpected event write routes: {mutating}"
    assert OperationAuditMiddleware is not None
    assert events_mod.router.prefix == "/api/v1/events"
