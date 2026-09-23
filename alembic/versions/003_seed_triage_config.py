"""Seed triage system_config defaults."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "003_seed_triage_config"
down_revision = "002_seed_ingestion_config"
branch_labels = None
depends_on = None

CATEGORY_RISK = {
    "brute_force": 90,
    "malware": 95,
    "web_attack": 85,
    "network_intrusion": 88,
    "file_integrity": 70,
    "login_anomaly": 75,
    "authentication": 60,
    "firewall": 55,
    "windows_event": 50,
    "host_anomaly": 65,
    "syslog": 40,
    "compliance": 35,
    "data_exfiltration": 92,
    "privilege_escalation": 93,
    "uncategorized": 50,
}

ROWS = [
    ("triage.dedup_window_minutes", {"value": 60}, "Dedup sliding window in minutes"),
    ("triage.deep_review_threshold", {"value": 70}, "Effective score threshold for deep review queue"),
    ("triage.low_risk_threshold", {"value": 30}, "Below this score alerts may be archived as low risk"),
    ("triage.uncertain_band_low", {"value": 30}, "Lower bound of uncertain score band"),
    ("triage.uncertain_band_high", {"value": 70}, "Upper bound of uncertain score band"),
    ("triage.sample_audit_rate", {"value": 0.01}, "Random audit rate for archived low-risk alerts"),
    ("triage.llm_assist_enabled", {"value": False}, "Enable optional LLM assist scoring in triage"),
    ("triage.llm_weight", {"value": 0.15}, "LLM weight in effective triage score"),
    ("triage.batch_size", {"value": 500}, "Max NEW alerts processed per triage run"),
    ("triage.poll_interval_minutes", {"value": 2}, "Interval between triage scheduler runs"),
    ("triage.category_risk", {"weights": CATEGORY_RISK}, "Static category risk weights"),
]


def upgrade() -> None:
    table = sa.table(
        "system_config",
        sa.column("key", sa.String),
        sa.column("value", JSONB),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        table,
        [{"key": key, "value": value, "description": desc} for key, value, desc in ROWS],
    )


def downgrade() -> None:
    keys = ", ".join(f"'{key}'" for key, _, _ in ROWS)
    op.execute(sa.text(f"DELETE FROM system_config WHERE key IN ({keys})"))
