"""Scoped API key scope catalog and high-risk / pipeline matrices (P0-02).

O-07 / O-10 remain Proposed; this module encodes the kickoff defaults so
behavior is testable and documented for PO confirmation.
"""

from __future__ import annotations

# Scopes that may be granted to DB-backed keys. None imply Admin.
# T-KEY-07: no scope alias elevates to role=admin.
ALLOWED_SCOPES: frozenset[str] = frozenset(
    {
        "events:read",
        "alerts:read",
        "dashboard:read",
        "investigations:read",
        "ingestion:pull",
        "pipeline:run:triage",
        "pipeline:run:aggregation",
        "pipeline:run:ingestion",
        "pipeline:run:investigation",
        "pipeline:run:human_review",
        "pipeline:run:defense_assets",
        "pipeline:run:regression",
        "pipeline:run:health_check",
    }
)

# Forbidden scope strings (reject at create/rotate).
FORBIDDEN_SCOPE_TOKENS: frozenset[str] = frozenset(
    {
        "admin",
        "*",
        "role:admin",
        "users:write",
        "config:write",
        "license:write",
        "api_keys:write",
    }
)

# O-07 Proposed: JWT Admin only (not legacy key, not scoped keys).
HIGH_RISK_ROUTE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("PUT", "/api/v1/system/config"),
    ("POST", "/api/v1/users"),
    ("POST", "/api/v1/license/import"),
    ("POST", "/api/v1/api-keys"),
    ("DELETE", "/api/v1/api-keys"),
    ("POST", "/api/v1/api-keys/"),  # rotate / revoke under id
)

# Paths that are high-risk even for GET if they mutate via POST patterns —
# matched by prefix for POST/PUT/PATCH/DELETE under these roots.
HIGH_RISK_PATH_PREFIXES: tuple[str, ...] = (
    "/api/v1/system/config",
    "/api/v1/users",
    "/api/v1/license",
    "/api/v1/api-keys",
    # P0-09 enable-suppression (when added) must stay JWT-admin-only (O-07).
    "/api/v1/whitelist-rules",
)

# O-10 Proposed: Operator JWT may manually run these pipelines; Admin may run all.
OPERATOR_ALLOWED_PIPELINES: frozenset[str] = frozenset(
    {
        "triage",
        "aggregation",
        "ingestion",
    }
)

ADMIN_ONLY_PIPELINES: frozenset[str] = frozenset(
    {
        "investigation",
        "human_review",
        "defense_assets",
        "regression",
        "health_check",
    }
)


def validate_scopes(scopes: list[str]) -> list[str]:
    cleaned: list[str] = []
    for raw in scopes:
        scope = (raw or "").strip().lower()
        if not scope:
            continue
        if scope in FORBIDDEN_SCOPE_TOKENS or any(
            scope == f or scope.startswith(f + ":") for f in ("admin", "role")
        ):
            raise ValueError(f"Scope not allowed (no admin elevation): {raw}")
        if scope not in ALLOWED_SCOPES:
            raise ValueError(f"Unknown scope: {raw}")
        if scope not in cleaned:
            cleaned.append(scope)
    if not cleaned:
        raise ValueError("At least one valid scope is required")
    return cleaned


def is_high_risk_request(method: str, path: str) -> bool:
    m = method.upper()
    if m not in {"POST", "PUT", "PATCH", "DELETE"}:
        return False
    normalized = path.rstrip("/") or "/"
    for prefix in HIGH_RISK_PATH_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return True
    return False


def pipeline_scope(pipeline: str) -> str:
    return f"pipeline:run:{pipeline}"


def can_run_pipeline(
    *,
    is_admin: bool,
    role: str,
    via_legacy_api_key: bool,
    scopes: list[str] | None,
    pipeline: str,
) -> bool:
    """Whether the caller may manually run a named pipeline."""
    if is_admin and not via_legacy_api_key:
        return True
    scope = pipeline_scope(pipeline)
    if scopes:
        if scope in scopes:
            return True
        # Alias: ingestion:pull covers ingestion pipeline / pull endpoints.
        if pipeline == "ingestion" and "ingestion:pull" in scopes:
            return True
    # Legacy env key: operator-class pipelines only (not admin-only).
    if via_legacy_api_key:
        return pipeline in OPERATOR_ALLOWED_PIPELINES
    # JWT operator (no scopes)
    if role == "operator" and not scopes:
        return pipeline in OPERATOR_ALLOWED_PIPELINES
    return False


# Read-only path prefix → required scope (scoped keys only).
_READ_SCOPE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("/api/v1/events", "events:read"),
    ("/api/v1/alerts", "alerts:read"),
    ("/api/v1/dashboard", "dashboard:read"),
    ("/api/v1/investigations", "investigations:read"),
    ("/api/v1/human-review", "investigations:read"),
    ("/api/v1/morning-note", "dashboard:read"),
    ("/api/v1/playbooks", "investigations:read"),
    ("/api/v1/console/pending", "dashboard:read"),
)

_PIPELINE_RUN_PATHS: dict[str, str] = {
    "/api/v1/triage/run": "pipeline:run:triage",
    "/api/v1/aggregation/run": "pipeline:run:aggregation",
    "/api/v1/investigations/run": "pipeline:run:investigation",
    "/api/v1/human-review/run": "pipeline:run:human_review",
    "/api/v1/defense-assets/run": "pipeline:run:defense_assets",
    "/api/v1/regression/run": "pipeline:run:regression",
    "/api/v1/health-checks/run": "pipeline:run:health_check",
}


def scoped_key_allows_request(method: str, path: str, scopes: list[str] | None) -> bool:
    """Return True if a scoped API key may call this route (T-KEY-07 limited).

    Scopes never grant admin / high-risk routes (those are blocked separately).
    """
    if not scopes:
        return False
    m = method.upper()
    p = path.rstrip("/") or "/"
    granted = set(scopes)

    if m == "GET" and p == "/api/v1/auth/me":
        return True

    if m == "POST" and p.startswith("/api/v1/console/run/"):
        pipe = p.removeprefix("/api/v1/console/run/")
        return can_run_pipeline(
            is_admin=False,
            role="operator",
            via_legacy_api_key=False,
            scopes=list(granted),
            pipeline=pipe,
        )

    if m == "POST" and p in _PIPELINE_RUN_PATHS:
        needed = _PIPELINE_RUN_PATHS[p]
        return needed in granted or (
            needed == "pipeline:run:ingestion" and "ingestion:pull" in granted
        )

    if m == "POST" and (p.startswith("/api/v1/ingestion/") or p == "/api/v1/ingestion"):
        return "ingestion:pull" in granted or "pipeline:run:ingestion" in granted

    if m == "GET":
        for prefix, scope in _READ_SCOPE_PREFIXES:
            if p == prefix or p.startswith(prefix + "/"):
                return scope in granted
        return False

    # No other mutations for scoped keys (disposition / whitelist / config / users…).
    return False
