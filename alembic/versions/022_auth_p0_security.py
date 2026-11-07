"""P0-01: must_change_password, token_version, mfa_grace_until; admin MFA required."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "022_auth_p0_security"
down_revision = "021_investigation_ops_failure"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column("users", sa.Column("mfa_grace_until", sa.DateTime(), nullable=True))

    # Existing admins: require MFA + force password change (no password hash reset).
    op.execute(
        sa.text(
            """
            UPDATE users
            SET mfa_required = true,
                must_change_password = true
            WHERE is_admin = true OR role = 'admin'
            """
        )
    )


def downgrade() -> None:
    op.drop_column("users", "mfa_grace_until")
    op.drop_column("users", "token_version")
    op.drop_column("users", "must_change_password")
