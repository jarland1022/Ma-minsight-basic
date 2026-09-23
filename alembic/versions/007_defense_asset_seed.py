"""Seed defense asset configuration."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "007_defense_asset_seed"
down_revision = "006_human_review_seed"
branch_labels = None
depends_on = None

CONFIG_ROWS = [
    ("defense_assets.enabled", {"value": True}, "Enable defense asset sedimentation"),
    ("defense_assets.poll_interval_minutes", {"value": 5}, "Asset pipeline scheduler interval"),
    ("defense_assets.batch_size", {"value": 20}, "Max events settled per run"),
    ("defense_assets.auto_close_event", {"value": True}, "Close event after judgment case written"),
    (
        "defense_assets.require_disposition_confirm",
        {"value": False},
        "Require disposition confirm before closing event",
    ),
    ("defense_assets.whitelist_promotion_threshold", {"value": 3}, "Confirmations to promote whitelist"),
    ("defense_assets.whitelist_rule_ttl_days", {"value": 365}, "Promoted whitelist rule validity days"),
    (
        "defense_assets.create_whitelist_on_fp_only",
        {"value": True},
        "Only create whitelist candidates for false positive verdicts",
    ),
    ("defense_assets.embedding_enabled", {"value": False}, "Compute judgment case embeddings"),
    ("defense_assets.embedding_search_enabled", {"value": False}, "Use embedding search in Agent prompt"),
    ("defense_assets.embedding_model", {"value": "text-embedding-3-small"}, "Embedding model name"),
    ("audit_sample.auto_confirm_whitelist", {"value": False}, "Audit sample FP auto-confirms whitelist"),
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
