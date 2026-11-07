"""P0-08: additive audit_logs result / correlation_id / client_ip.

Compatible with existing rows (all new columns nullable).
Rollback drops only these additive columns; historical detail JSONB retained.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "023_audit_p0_security"
down_revision = "022_auth_p0_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("result", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "audit_logs",
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "audit_logs",
        sa.Column("client_ip", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_audit_logs_result", "audit_logs", ["result"])
    op.create_index("ix_audit_logs_correlation_id", "audit_logs", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_correlation_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_result", table_name="audit_logs")
    op.drop_column("audit_logs", "client_ip")
    op.drop_column("audit_logs", "correlation_id")
    op.drop_column("audit_logs", "result")
