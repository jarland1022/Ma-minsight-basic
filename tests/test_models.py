"""Smoke tests for ORM metadata."""

from app.db.base import Base
import app.models  # noqa: F401


def test_all_tables_registered() -> None:
    expected = {
        "alert_dedup_groups",
        "alerts",
        "api_keys",
        "audit_logs",
        "audit_samples",
        "cache_entries",
        "data_sources",
        "disposition_records",
        "entity_profile_memories",
        "entity_profile_stats",
        "entity_profiles",
        "event_alerts",
        "events",
        "health_check_runs",
        "health_check_scenarios",
        "human_review_requests",
        "human_review_responses",
        "investigation_conclusions",
        "investigation_messages",
        "investigation_sops",
        "investigation_tool_calls",
        "investigations",
        "judgment_cases",
        "on_duty_knowledge",
        "profile_update_suggestions",
        "regression_test_cases",
        "regression_test_runs",
        "rule_candidates",
        "system_config",
        "threat_intel_entries",
        "triage_results",
        "users",
        "whitelist_candidates",
        "whitelist_rules",
    }
    assert set(Base.metadata.tables.keys()) == expected


def test_profile_memory_separate_from_whitelist() -> None:
    """Methodology #6: memories and whitelist rules must remain separate tables."""
    memory_table = Base.metadata.tables["entity_profile_memories"]
    whitelist_table = Base.metadata.tables["whitelist_rules"]
    assert memory_table.name != whitelist_table.name
    assert "entity_profile_id" in {c.name for c in memory_table.columns}
    assert "match_pattern" in {c.name for c in whitelist_table.columns}


def test_event_aggregation_dimensions() -> None:
    """Option B: host + user + category + 24h window columns on events."""
    events = Base.metadata.tables["events"]
    column_names = {c.name for c in events.columns}
    assert {
        "aggregate_host_name",
        "aggregate_user_name",
        "aggregate_category",
        "aggregate_window_start",
        "event_key",
    }.issubset(column_names)


def test_event_has_queue_priority_column() -> None:
    events = Base.metadata.tables["events"]
    assert "queue_priority" in {c.name for c in events.columns}


def test_event_alerts_unique_alert_id() -> None:
    table = Base.metadata.tables["event_alerts"]
    constraint_names = {c.name for c in table.constraints if hasattr(c, "name") and c.name}
    assert "uq_event_alerts_alert_id" in constraint_names


def test_judgment_case_embedding_reserved() -> None:
    cases = Base.metadata.tables["judgment_cases"]
    embedding = cases.columns["embedding"]
    assert embedding.nullable is True
