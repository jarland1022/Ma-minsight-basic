"""Seed default system_config keys for ingestion."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "002_seed_ingestion_config"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = sa.table(
        "system_config",
        sa.column("key", sa.String),
        sa.column("value", JSONB),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        table,
        [
            {
                "key": "ingestion.poll_interval_minutes",
                "value": {"value": 5},
                "description": "Interval in minutes between scheduled ingestion polls",
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM system_config WHERE key = 'ingestion.poll_interval_minutes'")
    )
