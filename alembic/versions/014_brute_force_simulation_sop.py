"""Add simulate_disposition to brute_force SOP recommended skills."""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "014_brute_force_simulation_sop"
down_revision = "013_disposition_simulations"
branch_labels = None
depends_on = None

RECOMMENDED_SKILLS = [
    "query_entity_graph",
    "query_asset",
    "query_history_alerts",
    "query_threat_intel",
    "simulate_disposition",
]


def upgrade() -> None:
    skills_json = json.dumps(RECOMMENDED_SKILLS, ensure_ascii=False)
    op.execute(
        sa.text(
            """
            UPDATE investigation_sops
            SET recommended_skills = CAST(:skills AS jsonb),
                updated_at = NOW()
            WHERE alert_category = 'brute_force' AND is_active = true
            """
        ).bindparams(skills=skills_json)
    )


def downgrade() -> None:
    legacy = json.dumps(
        ["query_entity_graph", "query_asset", "query_history_alerts", "query_threat_intel"],
        ensure_ascii=False,
    )
    op.execute(
        sa.text(
            """
            UPDATE investigation_sops
            SET recommended_skills = CAST(:skills AS jsonb),
                updated_at = NOW()
            WHERE alert_category = 'brute_force' AND is_active = true
            """
        ).bindparams(skills=legacy)
    )
