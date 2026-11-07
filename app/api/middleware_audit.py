"""HTTP request-level operation audit middleware (P0-08).

## Middleware vs business audit (contract)

| Layer | Action naming | When written | Fail mode | Purpose |
|-------|---------------|--------------|-----------|---------|
| **Middleware** (`http.*`) | `http.get/post/put/...` | After response | Soft (never break HTTP) | Request envelope: method, path, status, actor, correlation_id |
| **Business** | `config.update`, `pipeline.manual_run`, `disposition.*`, … | In route / service | Fail-closed for high-risk; STARTED→SUCCESS/FAILED for pipelines | Semantic security event with before/after, result, phase |

Rules:
1. Middleware is **not** a substitute for business audits. Admins querying security
   history should filter on business actions (or `detail.event_level=business`).
2. Both layers share the same `X-Correlation-ID` so a single mutation can be
   reconstructed as request + business rows.
3. Middleware detail includes `event_level=request`; business helpers set
   `event_level=business`.
4. Auth login/MFA paths are skipped here because routes write dedicated auth.* rows.
"""

from __future__ import annotations

import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.correlation import CORRELATION_HEADER, get_or_create_correlation_id
from app.db.enums import ActorType
from app.db import session as db_session
from app.services.audit import AuditResult, write_audit

logger = logging.getLogger(__name__)

_SKIP_PREFIXES = (
    "/health",
    "/docs",
    "/openapi",
    "/redoc",
    "/api/v1/auth/login",
    "/api/v1/auth/mfa/",
)

_PILOT_VIEW_PREFIXES = (
    "/api/v1/events",
    "/api/v1/alerts",
    "/api/v1/investigations",
    "/api/v1/morning-note",
    "/api/v1/dashboard",
    "/api/v1/playbooks",
    "/api/v1/human-review",
)


def _status_to_result(status_code: int) -> AuditResult:
    if status_code < 400:
        return AuditResult.SUCCESS
    if status_code in {401, 403}:
        return AuditResult.DENIED
    return AuditResult.FAILURE


class OperationAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        correlation_id = get_or_create_correlation_id(request)
        response = await call_next(request)
        response.headers.setdefault(CORRELATION_HEADER, correlation_id)

        try:
            path = request.url.path
            if any(path.startswith(p) for p in _SKIP_PREFIXES):
                return response
            if not path.startswith("/api/v1/"):
                return response

            auth = getattr(request.state, "auth", None)
            method = request.method.upper()
            should_log = False
            if method in {"POST", "PUT", "PATCH", "DELETE"}:
                should_log = True
            elif (
                method == "GET"
                and auth is not None
                and getattr(auth, "is_readonly", False)
                and any(path.startswith(p) for p in _PILOT_VIEW_PREFIXES)
            ):
                should_log = True

            if not should_log:
                return response

            client_ip = getattr(auth, "client_ip", None)
            if client_ip is None and request.client:
                client_ip = request.client.host

            async with db_session.async_session_factory() as session:
                await write_audit(
                    session,
                    action=f"http.{method.lower()}",
                    actor_type=ActorType.USER,
                    actor_id=getattr(auth, "user_id", None) or getattr(auth, "username", None),
                    resource_type="http",
                    resource_id=f"{method} {path}",
                    detail={
                        "event_level": "request",
                        "status_code": response.status_code,
                        "role": getattr(auth, "role", None),
                        "readonly": bool(getattr(auth, "is_readonly", False)),
                    },
                    result=_status_to_result(response.status_code),
                    correlation_id=correlation_id,
                    client_ip=client_ip,
                    commit=True,
                    fail_closed=False,
                )
        except Exception:
            logger.exception(
                "operation audit middleware failed correlation_id=%s",
                correlation_id,
            )
        return response
