"""Pilot readonly accounts: role, expiry, IP allowlist."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "019_pilot_accounts"
down_revision = "018_conclusion_disposition_grade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=32), nullable=False, server_default="operator"),
    )
    op.add_column("users", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("revoked_at", sa.DateTime(), nullable=True))
    op.add_column(
        "users",
        sa.Column("allowed_cidrs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("users", sa.Column("pilot_label", sa.String(length=256), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("last_login_ip", sa.String(length=64), nullable=True))
    op.execute("UPDATE users SET role = 'admin' WHERE is_admin IS TRUE")
    op.execute("UPDATE users SET role = 'operator' WHERE is_admin IS NOT TRUE")


def downgrade() -> None:
    op.drop_column("users", "last_login_ip")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "pilot_label")
    op.drop_column("users", "allowed_cidrs")
    op.drop_column("users", "revoked_at")
    op.drop_column("users", "expires_at")
    op.drop_column("users", "role")
