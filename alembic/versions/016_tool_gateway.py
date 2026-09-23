"""EP-09: tool gateway credentials table and config seeds."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, insert

revision = "016_tool_gateway"
down_revision = "015_phase2_completion"
branch_labels = None
depends_on = None

CONFIG_ROWS = [
    ("tools.gateway_enabled", {"value": False}, "是否启用统一工具网关"),
    ("tools.gateway_timeout_seconds", {"value": 30}, "工具网关 HTTP 超时（秒）"),
    ("tools.gateway_audit_all_calls", {"value": True}, "是否审计所有网关调用"),
]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "tool_gateway_credentials" not in insp.get_table_names():
        op.create_table(
            "tool_gateway_credentials",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("adapter_name", sa.String(64), nullable=False),
            sa.Column("credential_ref", sa.String(256), nullable=False),
            sa.Column("description", sa.String(512), nullable=True),
            sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("adapter_name", "credential_ref", name="uq_tool_gateway_cred"),
        )
        op.create_index(
            "ix_tool_gateway_credentials_adapter",
            "tool_gateway_credentials",
            ["adapter_name"],
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
    op.drop_index("ix_tool_gateway_credentials_adapter", table_name="tool_gateway_credentials")
    op.drop_table("tool_gateway_credentials")
