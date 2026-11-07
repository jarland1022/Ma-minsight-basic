"""P0-03/05: structured investigation ops failure + HR cancel audit fields."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "021_investigation_ops_failure"
down_revision = "020_pilot_mfa_reserved"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("investigations", sa.Column("failure_class", sa.String(length=64), nullable=True))
    op.add_column("investigations", sa.Column("error_code", sa.String(length=64), nullable=True))
    op.add_column(
        "investigations",
        sa.Column("failure_detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.add_column(
        "investigation_conclusions",
        sa.Column(
            "invalidated_as_ops_failure",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "investigation_conclusions",
        sa.Column("invalidated_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "investigation_conclusions",
        sa.Column("invalidated_reason", sa.Text(), nullable=True),
    )

    op.add_column("human_review_requests", sa.Column("cancel_reason", sa.Text(), nullable=True))
    op.add_column("human_review_requests", sa.Column("cancelled_at", sa.DateTime(), nullable=True))
    op.add_column(
        "human_review_requests",
        sa.Column("cancelled_by", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("human_review_requests", "cancelled_by")
    op.drop_column("human_review_requests", "cancelled_at")
    op.drop_column("human_review_requests", "cancel_reason")
    op.drop_column("investigation_conclusions", "invalidated_reason")
    op.drop_column("investigation_conclusions", "invalidated_at")
    op.drop_column("investigation_conclusions", "invalidated_as_ops_failure")
    op.drop_column("investigations", "failure_detail")
    op.drop_column("investigations", "error_code")
    op.drop_column("investigations", "failure_class")
