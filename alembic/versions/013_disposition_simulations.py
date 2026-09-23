"""EP-07: disposition impact simulations (read-only, approval queue)."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, insert

revision = "013_disposition_simulations"
down_revision = "012_phase2_core"
branch_labels = None
depends_on = None

CONFIG_ROWS = [
    ("disposition.simulation_enabled", {"value": False}, "是否启用处置推演 Skill"),
    ("disposition.require_approval", {"value": True}, "推演结果是否需 Web 审批"),
    (
        "disposition.allowed_action_types",
        {"value": ["block_ip", "isolate_host", "disable_user"]},
        "允许推演的处置动作类型",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "disposition_simulations" not in insp.get_table_names():
        op.create_table(
            "disposition_simulations",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("investigation_id", sa.UUID(), nullable=False),
            sa.Column("action_type", sa.String(64), nullable=False),
            sa.Column("action_params", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("simulated_impact", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column(
                "approval_status",
                sa.String(32),
                nullable=False,
                server_default="draft",
            ),
            sa.Column("approved_by_id", sa.UUID(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_disposition_simulations_inv",
            "disposition_simulations",
            ["investigation_id"],
        )

    config_table = sa.table(
        "system_config",
        sa.column("key", sa.String),
        sa.column("value", JSONB),
        sa.column("description", sa.Text),
    )
    for key, value, desc in CONFIG_ROWS:
        stmt = insert(config_table).values(key=key, value=value, description=desc)
        op.execute(stmt.on_conflict_do_nothing(index_elements=["key"]))


def downgrade() -> None:
    keys = ", ".join(f"'{k}'" for k, _, _ in CONFIG_ROWS)
    op.execute(sa.text(f"DELETE FROM system_config WHERE key IN ({keys})"))
    op.drop_index("ix_disposition_simulations_inv", table_name="disposition_simulations")
    op.drop_table("disposition_simulations")
