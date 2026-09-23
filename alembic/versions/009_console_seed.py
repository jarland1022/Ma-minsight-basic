"""Seed admin user and console configuration."""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "009_console_seed"
down_revision = "008_pgvector_extension"
branch_labels = None
depends_on = None

CONFIG_ROWS = [
    ("console.session_expire_hours", {"value": 8}, "JWT session expire hours"),
    ("console.page_size_default", {"value": 20}, "Default list page size"),
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

    import bcrypt

    password = os.environ.get("ADMIN_INITIAL_PASSWORD", "changeme")
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    op.execute(
        sa.text(
            """
            INSERT INTO users (id, username, email, password_hash, is_active, is_admin, created_at, updated_at)
            SELECT gen_random_uuid(), 'admin', 'admin@localhost', :ph, true, true, NOW(), NOW()
            WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin')
            """
        ).bindparams(ph=password_hash)
    )


def downgrade() -> None:
    keys = ", ".join(f"'{k}'" for k, _, _ in CONFIG_ROWS)
    op.execute(sa.text(f"DELETE FROM system_config WHERE key IN ({keys})"))
    op.execute(sa.text("DELETE FROM users WHERE username = 'admin'"))
