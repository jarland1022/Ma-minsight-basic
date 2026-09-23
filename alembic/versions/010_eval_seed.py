"""Seed eval config, health_probe source, regression cases, health scenarios."""

from __future__ import annotations

import json
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID, insert

from app.db.enums import HealthCheckStage, InvestigationVerdict

revision = "010_eval_seed"
down_revision = "009_console_seed"
branch_labels = None
depends_on = None

CONFIG_ROWS = [
    ("eval.regression_enabled", {"value": True}, "Enable regression test runner"),
    ("eval.regression_use_real_llm_default", {"value": False}, "Default use real LLM for regression"),
    ("eval.regression_cron", {"value": None}, "Cron for regression (null=disabled)"),
    ("eval.health_check_enabled", {"value": True}, "Enable health check runner"),
    ("eval.health_check_cron", {"value": None}, "Cron for health checks (null=disabled)"),
    (
        "eval.health_check_agent_mock_verdict",
        {"value": "likely_false_positive"},
        "Mock verdict for health-check agent stage",
    ),
    ("eval.probe_retention_days", {"value": 7}, "Days to retain probe alerts/events"),
    ("eval.alert_webhook_url", {"value": None}, "Optional webhook URL on eval failure"),
]

AUTH_FAILED_PAYLOAD = {
    "_id": "health-seed-auth-failed",
    "timestamp": "2026-06-23T08:15:30.000Z",
    "rule": {
        "id": "5710",
        "level": 10,
        "description": "sshd: authentication failed.",
        "groups": ["authentication_failed", "syslog", "sshd"],
    },
    "agent": {"id": "001", "name": "web-server-01", "ip": "10.0.1.10"},
    "data": {"srcip": "203.0.113.50", "dstuser": "root", "srcport": 54321},
    "decoder": {"name": "sshd"},
    "location": "/var/log/auth.log",
    "full_log": "Failed password for root from 203.0.113.50 port 54321 ssh2",
}

REGRESSION_CASES = [
    {
        "name": "brute_force_fp",
        "alert_payload": {
            "rule_id": "5710",
            "rule_name": "sshd authentication failed",
            "severity": 4,
            "src_ip": "203.0.113.50",
            "user_name": "root",
            "host_name": "web-server-01",
            "alert_category": "brute_force",
            "occurred_at": "2026-06-23T08:15:30Z",
        },
        "expected_verdict": InvestigationVerdict.LIKELY_FALSE_POSITIVE,
        "expected_skills": ["query_asset", "query_history_alerts"],
        "forbidden_skills": None,
        "tags": ["brute_force", "agent"],
    },
    {
        "name": "brute_force_attack",
        "alert_payload": {
            "rule_id": "5710",
            "rule_name": "sshd authentication failed",
            "severity": 5,
            "src_ip": "203.0.113.99",
            "user_name": "admin",
            "host_name": "web-server-02",
            "alert_category": "brute_force",
            "occurred_at": "2026-06-23T09:00:00Z",
        },
        "expected_verdict": InvestigationVerdict.ATTACK_CONFIRMED,
        "expected_skills": ["query_asset", "query_history_alerts"],
        "forbidden_skills": None,
        "tags": ["brute_force", "agent"],
    },
    {
        "name": "insufficient_geo",
        "alert_payload": {
            "rule_id": "5716",
            "rule_name": "sshd unusual login",
            "severity": 4,
            "src_ip": "198.51.100.20",
            "user_name": "admin",
            "host_name": "vpn-gateway",
            "alert_category": "authentication",
            "occurred_at": "2026-06-23T10:00:00Z",
        },
        "expected_verdict": InvestigationVerdict.INSUFFICIENT_INFORMATION,
        "expected_skills": ["query_asset"],
        "forbidden_skills": None,
        "tags": ["authentication", "agent"],
    },
    {
        "name": "needs_human",
        "alert_payload": {
            "rule_id": "31103",
            "rule_name": "web attack probe",
            "severity": 4,
            "src_ip": "198.51.100.10",
            "host_name": "web-server-02",
            "alert_category": "web_attack",
            "occurred_at": "2026-06-23T10:05:00Z",
        },
        "expected_verdict": InvestigationVerdict.NEEDS_HUMAN_REVIEW,
        "expected_skills": ["query_asset"],
        "forbidden_skills": None,
        "tags": ["web", "agent"],
    },
    {
        "name": "syscheck_benign",
        "alert_payload": {
            "rule_id": "550",
            "rule_name": "syscheck modified",
            "severity": 3,
            "host_name": "db-server-01",
            "alert_category": "syscheck",
            "occurred_at": "2026-06-23T11:00:00Z",
        },
        "expected_verdict": InvestigationVerdict.LIKELY_FALSE_POSITIVE,
        "expected_skills": ["query_asset"],
        "forbidden_skills": None,
        "tags": ["syscheck", "agent"],
    },
]

HEALTH_SCENARIOS = [
    {
        "name": "probe_ingest",
        "description": "Inject probe alert remains NEW",
        "inject_payload": AUTH_FAILED_PAYLOAD,
        "expected_stage": HealthCheckStage.INGESTION,
        "expected_outcome": {"alert_status": "new"},
    },
    {
        "name": "probe_triage_deep",
        "description": "High-risk auth failure routes to deep review",
        "inject_payload": AUTH_FAILED_PAYLOAD,
        "expected_stage": HealthCheckStage.TRIAGE,
        "expected_outcome": {"alert_status": "triaged", "route_decision": "queue_deep_review"},
    },
    {
        "name": "probe_aggregate",
        "description": "Triaged deep-review alert links to event",
        "inject_payload": AUTH_FAILED_PAYLOAD,
        "expected_stage": HealthCheckStage.AGGREGATION,
        "expected_outcome": {
            "alert_status": "event_linked",
            "route_decision": "queue_deep_review",
            "event_status": "pending_review",
        },
    },
    {
        "name": "probe_agent_mock",
        "description": "Agent completes with mock verdict",
        "inject_payload": AUTH_FAILED_PAYLOAD,
        "expected_stage": HealthCheckStage.AGENT,
        "expected_outcome": {
            "investigation_status": "completed",
            "event_status": "concluded",
            "verdict": "likely_false_positive",
        },
    },
    {
        "name": "probe_full_chain",
        "description": "End-to-end probe through mock agent",
        "inject_payload": AUTH_FAILED_PAYLOAD,
        "expected_stage": HealthCheckStage.FULL_CHAIN,
        "expected_outcome": {
            "alert_status": "event_linked",
            "route_decision": "queue_deep_review",
            "event_status": "concluded",
            "verdict": "likely_false_positive",
            "defense_skipped": True,
        },
    },
]


def upgrade() -> None:
    config_table = sa.table(
        "system_config",
        sa.column("key", sa.String),
        sa.column("value", JSONB),
        sa.column("description", sa.Text),
    )
    for key, value, desc in CONFIG_ROWS:
        stmt = insert(config_table).values(key=key, value=value, description=desc)
        op.execute(stmt.on_conflict_do_nothing(index_elements=["key"]))

    probe_source_id = str(uuid.uuid4())
    op.execute(
        sa.text(
            """
            INSERT INTO data_sources (id, name, adapter_type, config, cursor_state, is_active, created_at, updated_at)
            VALUES (:id, 'health_probe', 'health_probe', '{}'::jsonb, '{}'::jsonb, true, NOW(), NOW())
            ON CONFLICT (name) DO NOTHING
            """
        ).bindparams(id=probe_source_id)
    )

    verdict_enum = sa.Enum(
        InvestigationVerdict,
        name="investigationverdict",
        create_type=False,
    )
    case_table = sa.table(
        "regression_test_cases",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("alert_payload", JSONB),
        sa.column("expected_verdict", verdict_enum),
        sa.column("expected_skills", JSONB),
        sa.column("forbidden_skills", JSONB),
        sa.column("tags", JSONB),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        case_table,
        [
            {
                "id": uuid.uuid4(),
                "name": c["name"],
                "alert_payload": c["alert_payload"],
                "expected_verdict": c["expected_verdict"],
                "expected_skills": c["expected_skills"],
                "forbidden_skills": c["forbidden_skills"],
                "tags": c["tags"],
                "is_active": True,
            }
            for c in REGRESSION_CASES
        ],
    )

    stage_enum = sa.Enum(
        HealthCheckStage,
        name="healthcheckstage",
        create_type=False,
    )
    scenario_table = sa.table(
        "health_check_scenarios",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("inject_payload", JSONB),
        sa.column("expected_stage", stage_enum),
        sa.column("expected_outcome", JSONB),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        scenario_table,
        [
            {
                "id": uuid.uuid4(),
                "name": s["name"],
                "description": s["description"],
                "inject_payload": s["inject_payload"],
                "expected_stage": s["expected_stage"],
                "expected_outcome": s["expected_outcome"],
                "is_active": True,
            }
            for s in HEALTH_SCENARIOS
        ],
    )


def downgrade() -> None:
    keys = ", ".join(f"'{k}'" for k, _, _ in CONFIG_ROWS)
    op.execute(sa.text(f"DELETE FROM system_config WHERE key IN ({keys})"))
    op.execute(sa.text("DELETE FROM data_sources WHERE name = 'health_probe'"))
    names = ", ".join(f"'{c['name']}'" for c in REGRESSION_CASES)
    op.execute(sa.text(f"DELETE FROM regression_test_cases WHERE name IN ({names})"))
    snames = ", ".join(f"'{s['name']}'" for s in HEALTH_SCENARIOS)
    op.execute(sa.text(f"DELETE FROM health_check_scenarios WHERE name IN ({snames})"))
