"""Prove the 8 residual failures are unrelated to P0-08 audit code paths."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BASELINE_NODEIDS = [
    "tests/aggregation/test_event_key.py",
    "tests/core/test_config.py",
    "tests/skills/test_query_threat_intel_timezone.py",
    "tests/test_models.py",
    "tests/threat_intel/test_ip_utils.py",
    "tests/triage/test_dedup.py",
    "tests/triage/test_frequency_datetime.py",
]

P0_08_MARKERS = (
    "write_audit",
    "pipeline_audit",
    "redact_for_audit",
    "OperationAuditMiddleware",
    "correlation_id",
    "event_level",
    "begin_pipeline_audit",
)


def test_baseline_failure_files_do_not_depend_on_p0_08_audit() -> None:
    for rel in BASELINE_NODEIDS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for marker in P0_08_MARKERS:
            assert marker not in text, f"{rel} unexpectedly references P0-08 symbol {marker}"


def test_closure_doc_lists_eight_baseline_failures() -> None:
    doc = (ROOT / "docs/review/P0_08_PREEXISTING_FAILURE_BASELINE.md").read_text(encoding="utf-8")
    assert "test_floor_to_window_start_utc_midnight" in doc
    assert "test_assemble_database_urls_encodes_special_characters" in doc
    assert "test_utc_now_matches_postgres_timestamp_expectation" in doc
    assert "test_all_tables_registered" in doc
    assert "test_is_public_ip" in doc
    assert "test_dedup_hit_when_representative_exists" in doc
    assert "test_dedup_resets_expired_window" in doc
    assert "test_frequency_db_fallback_uses_naive_datetime" in doc
