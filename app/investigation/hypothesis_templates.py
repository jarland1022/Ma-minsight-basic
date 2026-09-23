"""Default hypothesis templates for investigation SOPs."""

from __future__ import annotations

from typing import Any

BRUTE_FORCE_HYPOTHESIS_TEMPLATE: dict[str, Any] = {
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
    "required_skills_before_conclude": [
        "query_asset",
        "query_threat_intel",
    ],
    "investigation_intent": "先假设攻击成立，再主动寻找反证；若反证充分则倾向误报。",
}

DEFAULT_TERMINATION_POLICY: dict[str, Any] = {
    "min_evidence_closure_score": 0.6,
    "min_refutation_coverage_for_attack": 0.5,
    "max_closure_retries": 2,
}
