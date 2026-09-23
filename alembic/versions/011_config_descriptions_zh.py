"""Seed Chinese descriptions for system_config."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "011_config_descriptions_zh"
down_revision = "010_eval_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.services.system_config_descriptions import CONFIG_DESCRIPTIONS_ZH

    conn = op.get_bind()
    for key, desc in CONFIG_DESCRIPTIONS_ZH.items():
        conn.execute(
            sa.text(
                "UPDATE system_config SET description = :desc, updated_at = NOW() WHERE key = :key"
            ),
            {"key": key, "desc": desc},
        )


def downgrade() -> None:
    pass
