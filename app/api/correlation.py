"""Request correlation ID helpers (P0-08)."""

from __future__ import annotations

from uuid import uuid4

from starlette.requests import Request

CORRELATION_HEADER = "X-Correlation-ID"
REQUEST_ID_HEADER = "X-Request-ID"


def get_or_create_correlation_id(request: Request) -> str:
    existing = getattr(request.state, "correlation_id", None)
    if isinstance(existing, str) and existing:
        return existing

    header = request.headers.get(CORRELATION_HEADER) or request.headers.get(REQUEST_ID_HEADER)
    if header and header.strip():
        cid = header.strip()[:64]
    else:
        cid = uuid4().hex
    request.state.correlation_id = cid
    return cid
