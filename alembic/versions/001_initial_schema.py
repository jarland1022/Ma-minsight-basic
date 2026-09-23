"""Initial schema: all 34 tables for MA-MinSight triage & investigation pipeline."""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all ORM tables in dependency order."""
    # Import here so Alembic loads models only during migration execution.
    from app.db.base import Base
    import app.models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    """Drop all ORM tables."""
    from app.db.base import Base
    import app.models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.drop_all(bind)
