"""Add events.queue_priority and event_alerts.alert_id uniqueness."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, insert

revision = "004_event_aggregation"
down_revision = "003_seed_triage_config"
branch_labels = None
depends_on = None

CONFIG_ROWS = [
    ("event.aggregation_window_hours", {"value": 24}, "UTC-aligned aggregation window hours"),
    ("event.aggregation_batch_size", {"value": 500}, "Max alerts aggregated per run"),
    ("event.aggregation_poll_interval_minutes", {"value": 2}, "Aggregation scheduler interval"),
    ("event.unknown_host_sentinel", {"value": "__unknown_host__"}, "Sentinel when host_name missing"),
    ("event.unknown_user_sentinel", {"value": "__unknown_user__"}, "Sentinel when user_name missing"),
]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    event_columns = {col["name"] for col in insp.get_columns("events")}
    if "queue_priority" not in event_columns:
        op.add_column(
            "events",
            sa.Column("queue_priority", sa.Integer(), nullable=False, server_default="0"),
        )

    alert_constraints = {c["name"] for c in insp.get_unique_constraints("event_alerts")}
    if "uq_event_alerts_alert_id" not in alert_constraints:
        op.create_unique_constraint("uq_event_alerts_alert_id", "event_alerts", ["alert_id"])

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

    bind = op.get_bind()
    insp = sa.inspect(bind)
    alert_constraints = {c["name"] for c in insp.get_unique_constraints("event_alerts")}
    if "uq_event_alerts_alert_id" in alert_constraints:
        op.drop_constraint("uq_event_alerts_alert_id", "event_alerts", type_="unique")

    event_columns = {col["name"] for col in insp.get_columns("events")}
    if "queue_priority" in event_columns:
        op.drop_column("events", "queue_priority")
