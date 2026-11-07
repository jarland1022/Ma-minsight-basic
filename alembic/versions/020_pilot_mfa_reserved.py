"""Reserve MFA fields for pilot/operator accounts (enforcement later)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "020_pilot_mfa_reserved"
down_revision = "019_pilot_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("mfa_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("mfa_secret", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "mfa_secret")
    op.drop_column("users", "mfa_required")
