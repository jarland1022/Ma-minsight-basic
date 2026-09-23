"""Phase 2: entity relations, SOP hypothesis templates, closure metrics, audits."""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB, insert

revision = "012_phase2_core"
down_revision = "011_config_descriptions_zh"
branch_labels = None
depends_on = None

HYPOTHESIS_TEMPLATE = {
    "version": 1,
    "default_hypotheses": [
        {"id": "h_attack", "label": "真实攻击", "priority": 1},
        {"id": "h_fp", "label": "误报/业务行为", "priority": 2},
    ],
    "supporting_hints": [
        {
            "id": "s_ti_malicious",
            "description": "威胁情报标记恶意",
            "weight": 0.3,
            "skill": "query_threat_intel",
        },
        {
            "id": "s_multi_alert",
            "description": "同实体多告警",
            "weight": 0.2,
            "skill": "query_history_alerts",
        },
        {
            "id": "s_graph_path",
            "description": "实体关联链显示异常路径",
            "weight": 0.2,
            "skill": "query_entity_graph",
        },
    ],
    "refuting_hints": [
        {
            "id": "r_scanner",
            "description": "已知扫描器/值班知识",
            "weight": 0.25,
            "skill": "query_asset",
        },
        {
            "id": "r_business",
            "description": "业务系统正常交互",
            "weight": 0.15,
            "skill": "query_entity_graph",
        },
    ],
    "required_skills_before_conclude": ["query_asset", "query_threat_intel"],
    "investigation_intent": "先假设攻击成立，再主动寻找反证；若反证充分则倾向误报。",
}

TERMINATION_POLICY = {
    "min_evidence_closure_score": 0.6,
    "min_refutation_coverage_for_attack": 0.5,
    "max_closure_retries": 2,
}

CONFIG_ROWS = [
    ("entity.graph_enabled", {"value": True}, "是否启用实体关系图 Skill"),
    ("entity.graph_max_hops", {"value": 2}, "实体图 BFS 最大跳数"),
    ("entity.graph_max_nodes", {"value": 30}, "实体图单次返回节点上限"),
    ("entity.relation_ttl_days", {"value": 365}, "实体关系默认有效天数"),
    ("investigation.hypothesis_template_enabled", {"value": True}, "是否注入结构化假设 SOP"),
    ("investigation.require_refutation_attempt", {"value": True}, "攻击确认前是否必须尝试反证"),
    ("investigation.min_refuting_hints_checked", {"value": 1}, "至少评估的反证线索数"),
    ("investigation.closure_enabled", {"value": True}, "是否启用外置证据闭合度校验"),
    ("investigation.min_evidence_closure_score", {"value": 0.6}, "最低证据闭合度分数"),
    ("investigation.min_refutation_coverage_for_attack", {"value": 0.5}, "攻击确认最低反证覆盖率"),
    ("investigation.max_closure_retries", {"value": 2}, "闭合度驳回后最大补查次数"),
    ("investigation.supervisor_enabled", {"value": True}, "是否启用调查监督审计"),
    ("investigation.supervisor_block_on_fail", {"value": False}, "监督失败是否强制转人工"),
    ("investigation.metrics_enabled", {"value": True}, "仪表盘是否展示调查成本指标"),
    ("investigation.target_tokens_per_event", {"value": 10000}, "单 Event 调查 Token 参考上限"),
    ("investigation.correlation_window_hours", {"value": 72}, "告警关联扩线窗口（小时）"),
    ("triage.llm_assist_route_filter", {"value": ["queue_uncertain"]}, "仅对这些路由启用初筛 LLM"),
    ("triage.llm_assist_max_per_run", {"value": 20}, "每轮初筛 LLM 辅助上限"),
    ("eval.require_closure_pass_for_regression", {"value": True}, "回归测试是否校验闭合度"),
]


# Created by 001_initial (entity_profiles.entity_type). Reuse without emitting CREATE TYPE.
ENTITY_TYPE = ENUM(
    "ip",
    "host",
    "user",
    "domain",
    name="entitytype",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "entity_relations" not in insp.get_table_names():
        op.create_table(
            "entity_relations",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("from_entity_type", ENTITY_TYPE, nullable=False),
            sa.Column("from_entity_key", sa.String(256), nullable=False),
            sa.Column("to_entity_type", ENTITY_TYPE, nullable=False),
            sa.Column("to_entity_key", sa.String(256), nullable=False),
            sa.Column("relation_type", sa.String(64), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
            sa.Column("source", sa.String(64), nullable=False, server_default="seed"),
            sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("valid_from", sa.DateTime(), nullable=True),
            sa.Column("valid_until", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_entity_relations_from", "entity_relations", ["from_entity_type", "from_entity_key"])
        op.create_index("ix_entity_relations_to", "entity_relations", ["to_entity_type", "to_entity_key"])
        op.create_index("ix_entity_relations_type", "entity_relations", ["relation_type"])

    sop_cols = {c["name"] for c in insp.get_columns("investigation_sops")}
    if "hypothesis_template" not in sop_cols:
        op.add_column("investigation_sops", sa.Column("hypothesis_template", JSONB(), nullable=True))
    if "termination_policy" not in sop_cols:
        op.add_column("investigation_sops", sa.Column("termination_policy", JSONB(), nullable=True))

    event_cols = {c["name"] for c in insp.get_columns("events")}
    if "entity_context_snapshot" not in event_cols:
        op.add_column("events", sa.Column("entity_context_snapshot", JSONB(), nullable=True))

    inv_cols = {c["name"] for c in insp.get_columns("investigations")}
    if "closure_requested_at" not in inv_cols:
        op.add_column("investigations", sa.Column("closure_requested_at", sa.DateTime(), nullable=True))
    if "closure_retry_count" not in inv_cols:
        op.add_column(
            "investigations",
            sa.Column("closure_retry_count", sa.Integer(), nullable=False, server_default="0"),
        )

    concl_cols = {c["name"] for c in insp.get_columns("investigation_conclusions")}
    for col_name, col_type in [
        ("hypotheses_evaluated", JSONB()),
        ("refutation_summary", sa.Text()),
        ("evidence_closure_score", sa.Float()),
        ("refutation_coverage", sa.Float()),
        ("closure_checks", JSONB()),
        ("closure_passed", sa.Boolean()),
    ]:
        if col_name not in concl_cols:
            op.add_column("investigation_conclusions", sa.Column(col_name, col_type, nullable=True))

    if "investigation_audits" not in insp.get_table_names():
        op.create_table(
            "investigation_audits",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("investigation_id", sa.UUID(), nullable=False),
            sa.Column("audit_type", sa.String(32), nullable=False),
            sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("findings", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("supervisor_model", sa.String(64), nullable=False, server_default="rules"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_investigation_audits_inv", "investigation_audits", ["investigation_id"])

    config_table = sa.table(
        "system_config",
        sa.column("key", sa.String),
        sa.column("value", JSONB),
        sa.column("description", sa.Text),
    )
    for key, value, desc in CONFIG_ROWS:
        stmt = insert(config_table).values(key=key, value=value, description=desc)
        op.execute(stmt.on_conflict_do_nothing(index_elements=["key"]))

    template_json = json.dumps(HYPOTHESIS_TEMPLATE, ensure_ascii=False)
    policy_json = json.dumps(TERMINATION_POLICY, ensure_ascii=False)
    op.execute(
        sa.text(
            """
            UPDATE investigation_sops
            SET hypothesis_template = CAST(:template AS jsonb),
                termination_policy = CAST(:policy AS jsonb),
                recommended_skills = '["query_entity_graph", "query_asset", "query_history_alerts", "query_threat_intel"]'::jsonb,
                updated_at = NOW()
            WHERE alert_category = 'brute_force' AND is_active = true
            """
        ).bindparams(template=template_json, policy=policy_json)
    )


def downgrade() -> None:
    keys = ", ".join(f"'{k}'" for k, _, _ in CONFIG_ROWS)
    op.execute(sa.text(f"DELETE FROM system_config WHERE key IN ({keys})"))
    op.drop_table("investigation_audits")
    for col in [
        "closure_passed",
        "closure_checks",
        "refutation_coverage",
        "evidence_closure_score",
        "refutation_summary",
        "hypotheses_evaluated",
    ]:
        op.drop_column("investigation_conclusions", col)
    op.drop_column("investigations", "closure_retry_count")
    op.drop_column("investigations", "closure_requested_at")
    op.drop_column("events", "entity_context_snapshot")
    op.drop_column("investigation_sops", "termination_policy")
    op.drop_column("investigation_sops", "hypothesis_template")
    op.drop_table("entity_relations")
