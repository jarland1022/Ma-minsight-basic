"""Seed human review configuration."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "006_human_review_seed"
down_revision = "005_investigation_seed"
branch_labels = None
depends_on = None

CONFIG_ROWS = [
    ("human_review.enabled", {"value": True}, "Enable IM human review dispatch"),
    ("human_review.channel", {"value": "wecom"}, "IM channel adapter type"),
    ("human_review.poll_interval_minutes", {"value": 2}, "Human review scheduler interval"),
    ("human_review.batch_size", {"value": 10}, "Max review requests sent per run"),
    ("human_review.timeout_hours", {"value": 24}, "Hours before sent request expires"),
    ("human_review.max_resend", {"value": 2}, "Max resends after expiry per event"),
    ("human_review.reinvestigation_enabled", {"value": True}, "Re-run Agent after human reply"),
    (
        "human_review.reinvestigation_counts_budget",
        {"value": False},
        "Whether reinvestigation counts toward daily budget",
    ),
    ("human_review.wecom_to_user", {"value": "@all"}, "WeCom recipient userid"),
    ("human_review.message_max_chars", {"value": 1800}, "Max outbound markdown length"),
    ("audit_sample.enabled", {"value": True}, "Enable audit sample generation"),
    ("audit_sample.notify_via_im", {"value": False}, "Push audit samples via IM"),
]


def upgrade() -> None:
    config_table = sa.table(
        "system_config",
        sa.column("key", sa.String),
        sa.column("value", JSONB),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        config_table,
        [{"key": k, "value": v, "description": d} for k, v, d in CONFIG_ROWS],
    )


def downgrade() -> None:
    keys = ", ".join(f"'{k}'" for k, _, _ in CONFIG_ROWS)
    op.execute(sa.text(f"DELETE FROM system_config WHERE key IN ({keys})"))
