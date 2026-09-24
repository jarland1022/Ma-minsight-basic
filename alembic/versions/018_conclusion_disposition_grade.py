"""Add evidence_strength and disposition_grade on investigation conclusions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "018_conclusion_disposition_grade"
down_revision = "017_health_probe_outcome"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "investigation_conclusions",
        sa.Column("evidence_strength", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "investigation_conclusions",
        sa.Column("disposition_grade", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("investigation_conclusions", "disposition_grade")
    op.drop_column("investigation_conclusions", "evidence_strength")
