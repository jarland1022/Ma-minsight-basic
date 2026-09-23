"""Fix probe_entity_graph expected_outcome (remove non-state key)."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "017_health_probe_outcome"
down_revision = "016_tool_gateway"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE health_check_scenarios
            SET expected_outcome = '{"investigation_status": "completed", "event_status": "concluded", "verdict": "likely_false_positive"}'::jsonb
            WHERE name = 'probe_entity_graph'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE health_check_scenarios
            SET expected_outcome = '{"investigation_status": "completed", "event_status": "concluded", "verdict": "likely_false_positive", "required_skills": ["query_entity_graph"]}'::jsonb
            WHERE name = 'probe_entity_graph'
            """
        )
    )
