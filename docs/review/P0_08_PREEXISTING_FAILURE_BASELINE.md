# Pre-existing test failure baseline (verified 2026-11-06; re-confirmed same day at P0-08 close)

Captured with:

```text
py -3 -m pytest <8 nodeids> --tb=line -q
→ 8 failed (same set as full-suite residual; re-confirmed at closure gate)
```

These failures are **outside** P0-08 audit modules (`app/services/audit*.py`, `app/api/middleware_audit.py`, `app/api/audit_helpers.py`, `app/services/pipeline_audit.py`, `alembic/versions/023_*`).

| # | Nodeid | Module under test | Failure class | Root cause (verified) |
|---|--------|-------------------|---------------|------------------------|
| 1 | `tests/aggregation/test_event_key.py::test_floor_to_window_start_utc_midnight` | aggregation event window | tz-aware vs naive equality | Expected aware UTC midnight; function returns naive datetime |
| 2 | `tests/core/test_config.py::test_assemble_database_urls_encodes_special_characters` | `app.core.config` | assertion on DSN dialect | Test expects `postgresql://`; settings emit `postgresql+psycopg2://` |
| 3 | `tests/skills/test_query_threat_intel_timezone.py::test_utc_now_matches_postgres_timestamp_expectation` | datetime utils / TI skill | microsecond ordering | Race between two `utc_now()` calls in assertion |
| 4 | `tests/test_models.py::test_all_tables_registered` | model registry snapshot | stale expected table set | Left set has extra: `tool_gateway_credentials`, `investigation_audits`, `entity_relations`, `disposition_simulations` |
| 5 | `tests/threat_intel/test_ip_utils.py::test_is_public_ip` | threat intel IP utils | logic / TEST-NET | `is_public_ip('203.0.113.1')` returns False |
| 6 | `tests/triage/test_dedup.py::test_dedup_hit_when_representative_exists` | `app.triage.handlers.dedup` | naive/aware compare | `TypeError` at dedup.py:51 |
| 7 | `tests/triage/test_dedup.py::test_dedup_resets_expired_window` | same | same | same TypeError |
| 8 | `tests/triage/test_frequency_datetime.py::test_frequency_db_fallback_uses_naive_datetime` | triage frequency / AlertSnapshot | pydantic ValidationError | Test fixture missing `id`, `data_source_id`, `source_alert_id`, `fingerprint` |

**P0-08 impact:** None of these nodeids import or assert on audit persistence, redaction, correlation_id, or middleware business actions.

**Tracking:** Fix in separate hygiene tickets; do not block P0-08 closure.
