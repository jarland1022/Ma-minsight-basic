"""P0-02: scoped API keys — additive scopes/revoked_at/rotated_from_id.

Compatible with existing api_keys rows (nullable new columns).
Creates api_keys table if missing (some installs never had an alembic create).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "024_scoped_api_keys_p0_02"
down_revision = "023_audit_p0_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = set(insp.get_table_names())

    if "api_keys" not in tables:
        op.create_table(
            "api_keys",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("key_hash", sa.String(128), nullable=False),
            sa.Column("key_prefix", sa.String(16), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("scopes", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rotated_from_id", UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
        )
        op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])
    else:
        cols = {c["name"] for c in insp.get_columns("api_keys")}
        if "scopes" not in cols:
            op.add_column(
                "api_keys",
                sa.Column(
                    "scopes",
                    JSONB(),
                    nullable=False,
                    server_default=sa.text("'[]'::jsonb"),
                ),
            )
        if "revoked_at" not in cols:
            op.add_column("api_keys", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
        if "rotated_from_id" not in cols:
            op.add_column(
                "api_keys",
                sa.Column("rotated_from_id", UUID(as_uuid=True), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "api_keys" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("api_keys")}
    if "rotated_from_id" in cols:
        op.drop_column("api_keys", "rotated_from_id")
    if "revoked_at" in cols:
        op.drop_column("api_keys", "revoked_at")
    if "scopes" in cols:
        op.drop_column("api_keys", "scopes")
