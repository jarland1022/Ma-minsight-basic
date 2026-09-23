"""Phase 2 completion: EP-06 columns, EP-08 regression seeds, config."""

from __future__ import annotations

import json
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID, insert

from app.db.enums import HealthCheckStage, InvestigationVerdict

revision = "015_phase2_completion"
down_revision = "014_brute_force_simulation_sop"
branch_labels = None
depends_on = None

CONFIG_ROWS = [
    ("investigation.auto_raise_priority_on_correlation", {"value": True}, "发现关联 Event 时提高 queue_priority"),
    ("eval.entity_graph_mock_fixtures", {"value": {}}, "回归测试用实体关系图 fixture"),
]

PHASE2_REGRESSION_CASES = [
    {
        "name": "phase2_entity_graph",
        "alert_payload": {
            "rule_id": "5710",
            "rule_name": "sshd authentication failed",
            "severity": 5,
            "src_ip": "10.0.1.10",
            "user_name": "root",
            "host_name": "web-server-01",
            "alert_category": "brute_force",
            "occurred_at": "2026-06-24T08:00:00Z",
        },
        "expected_verdict": InvestigationVerdict.ATTACK_CONFIRMED,
        "expected_skills": [
            "query_entity_graph",
            "query_asset",
            "query_history_alerts",
            "query_threat_intel",
        ],
        "forbidden_skills": None,
        "tags": ["entity_graph", "phase2", "agent"],
    },
    {
        "name": "phase2_refutation_fp",
        "alert_payload": {
            "rule_id": "5710",
            "rule_name": "sshd authentication failed",
            "severity": 4,
            "src_ip": "203.0.113.50",
            "user_name": "root",
            "host_name": "web-server-01",
            "alert_category": "brute_force",
            "occurred_at": "2026-06-24T09:00:00Z",
        },
        "expected_verdict": InvestigationVerdict.LIKELY_FALSE_POSITIVE,
        "expected_skills": ["query_entity_graph", "query_asset", "query_history_alerts"],
        "forbidden_skills": None,
        "tags": ["refutation", "phase2", "agent"],
    },
]

HEALTH_ENTITY_GRAPH = {
    "name": "probe_entity_graph",
    "description": "Agent mock path includes entity graph skill for probe event",
    "inject_payload": {
        "_id": "health-seed-entity-graph",
        "timestamp": "2026-06-24T08:00:00Z",
        "rule": {"id": "5710", "level": 10, "description": "sshd: authentication failed."},
        "agent": {"id": "001", "name": "web-server-01", "ip": "10.0.1.10"},
        "data": {"srcip": "10.0.1.10", "dstuser": "root"},
    },
    "expected_stage": HealthCheckStage.AGENT,
    "expected_outcome": {
        "investigation_status": "completed",
        "event_status": "concluded",
        "verdict": "likely_false_positive",
    },
}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    event_cols = {c["name"] for c in insp.get_columns("events")}
    if "correlation_key" not in event_cols:
        op.add_column("events", sa.Column("correlation_key", sa.String(128), nullable=True))
    if "related_event_ids" not in event_cols:
        op.add_column(
            "events",
            sa.Column("related_event_ids", ARRAY(UUID(as_uuid=True)), nullable=True),
        )

    config_table = sa.table(
        "system_config",
        sa.column("key", sa.String),
        sa.column("value", JSONB),
        sa.column("description", sa.Text),
    )
    for key, value, desc in CONFIG_ROWS:
        stmt = insert(config_table).values(key=key, value=value, description=desc)
        op.execute(stmt.on_conflict_do_nothing(index_elements=["key"]))

    verdict_enum = sa.Enum(InvestigationVerdict, name="investigationverdict", create_type=False)
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
    for case in PHASE2_REGRESSION_CASES:
        op.execute(
            sa.text(
                "DELETE FROM regression_test_cases WHERE name = :name"
            ).bindparams(name=case["name"])
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
            for c in PHASE2_REGRESSION_CASES
        ],
    )

    stage_enum = sa.Enum(HealthCheckStage, name="healthcheckstage", create_type=False)
    op.execute(sa.text("DELETE FROM health_check_scenarios WHERE name = 'probe_entity_graph'"))
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
                "name": HEALTH_ENTITY_GRAPH["name"],
                "description": HEALTH_ENTITY_GRAPH["description"],
                "inject_payload": HEALTH_ENTITY_GRAPH["inject_payload"],
                "expected_stage": HEALTH_ENTITY_GRAPH["expected_stage"],
                "expected_outcome": HEALTH_ENTITY_GRAPH["expected_outcome"],
                "is_active": True,
            }
        ],
    )


def downgrade() -> None:
    keys = ", ".join(f"'{k}'" for k, _, _ in CONFIG_ROWS)
    op.execute(sa.text(f"DELETE FROM system_config WHERE key IN ({keys})"))
    names = ", ".join(f"'{c['name']}'" for c in PHASE2_REGRESSION_CASES)
    op.execute(sa.text(f"DELETE FROM regression_test_cases WHERE name IN ({names})"))
    op.execute(sa.text("DELETE FROM health_check_scenarios WHERE name = 'probe_entity_graph'"))
    op.drop_column("events", "related_event_ids")
    op.drop_column("events", "correlation_key")
