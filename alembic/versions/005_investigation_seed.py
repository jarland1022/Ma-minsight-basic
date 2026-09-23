"""Seed investigation config and brute_force SOP."""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "005_investigation_seed"
down_revision = "004_event_aggregation"
branch_labels = None
depends_on = None

CONFIG_ROWS = [
    ("investigation.poll_interval_minutes", {"value": 3}, "Agent investigation scheduler interval"),
    ("investigation.batch_size", {"value": 5}, "Max events investigated per run"),
    ("investigation.max_steps", {"value": 15}, "Max ReAct steps per investigation"),
    ("investigation.max_skill_calls", {"value": 20}, "Max skill invocations per investigation"),
    ("investigation.daily_event_budget", {"value": 200}, "Daily deep investigation event budget"),
    ("investigation.model_name", {"value": "deepseek-chat"}, "Default LLM for investigations"),
    ("investigation.reasoner_enabled", {"value": False}, "Reserved: enable reasoner re-run"),
    ("investigation.alert_prompt_limit", {"value": 20}, "Max alerts injected into investigation prompt"),
]

SOP_GUIDANCE = """调查原则（暴力破解/认证失败类）：
1. 先确认源 IP、账号、主机资产归属，以及是否为已知扫描器/漏扫器。
2. 查询该 IP/账号 24h 内失败与成功登录记录；若存在成功登录需提高优先级。
3. 威胁情报仅作参考，unknown 不能当作恶意定论。
4. 证据不足时必须 verdict=insufficient_information，并填写 human_query 说明需人工确认什么。
5. 处置建议仅输出建议动作，不得假设已执行封禁/隔离。
推荐 Skill：query_asset, query_history_alerts, query_threat_intel
"""


def upgrade() -> None:
    config_table = sa.table(
        "system_config",
        sa.column("key", sa.String),
        sa.column("value", JSONB),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        config_table,
        [{"key": k, "value": v, "description": d} for k, v, d in CONFIG_ROWS],
    )

    sop_id = str(uuid.uuid4())
    op.execute(
        sa.text(
            """
            INSERT INTO investigation_sops
            (id, alert_category, name, guidance_text, recommended_skills, is_active, version, created_at, updated_at)
            VALUES
            (:id, 'brute_force', 'Brute Force Investigation SOP', :guidance,
             '["query_asset", "query_history_alerts", "query_threat_intel"]'::jsonb,
             true, 1, NOW(), NOW())
            """
        ).bindparams(id=sop_id, guidance=SOP_GUIDANCE)
    )


def downgrade() -> None:
    keys = ", ".join(f"'{k}'" for k, _, _ in CONFIG_ROWS)
    op.execute(sa.text(f"DELETE FROM system_config WHERE key IN ({keys})"))
    op.execute(sa.text("DELETE FROM investigation_sops WHERE alert_category = 'brute_force'"))
