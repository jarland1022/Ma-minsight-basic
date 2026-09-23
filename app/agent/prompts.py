"""Prompt assembly for Agent investigations."""

from __future__ import annotations

import json

from app.agent.context import InvestigationContext
from app.playbooks.loader import render_playbook_prompt_section


def build_system_prompt(ctx: InvestigationContext) -> str:
    parts = [
        "你是企业安全运营中心的资深分析 Agent。",
        "你必须基于 Skill 返回的多源证据做复核结论，不能臆测。",
        "若证据不足，必须使用 verdict=insufficient_information 并填写 human_query。",
        "处置动作只能是建议，recommended_action 中需体现「建议」措辞。",
        "实体画像 memories 与判例仅供参考(reference_only)，不得直接当作放行或定罪依据。",
    ]

    if ctx.sop:
        parts.append("\n## 调查 SOP（原则，非固定步骤）")
        parts.append(f"名称: {ctx.sop.name}")
        parts.append(ctx.sop.guidance_text)
        if ctx.sop.recommended_skills:
            parts.append(f"推荐 Skill: {', '.join(map(str, ctx.sop.recommended_skills))}")
        if ctx.hypothesis_template_enabled and ctx.sop.hypothesis_template:
            parts.append("\n## 假设模板（须覆盖支持/反证线索）")
            parts.extend(_render_hypothesis_template(ctx.sop.hypothesis_template))

    if ctx.playbooks:
        parts.extend(
            render_playbook_prompt_section([p.model_dump() for p in ctx.playbooks])
        )

    if ctx.reference_cases:
        parts.append("\n## 参考判例（仅供参考，不得直接复用结论）")
        parts.append(json.dumps(ctx.reference_cases, ensure_ascii=False, indent=2))

    if ctx.human_review_context:
        parts.append("\n## 人工协查回复（权威补充，优先级高于推测）")
        parts.append(f"原问题: {ctx.human_review_context.get('human_query', '')}")
        reply = ctx.human_review_context.get("parsed_content") or ctx.human_review_context.get(
            "raw_content", ""
        )
        parts.append(reply)

    if ctx.disposition_simulation_enabled:
        parts.append("\n## 处置推演（高影响动作前置）")
        parts.append(
            "若拟在 recommended_action 中建议封禁 IP、隔离主机、禁用账号、阻断访问等高影响动作，"
            "在调用 submit_conclusion 之前必须先调用 simulate_disposition 评估影响范围与业务中断风险。"
            "将推演要点（影响主机数、业务系统、预估中断）写入 recommended_action 或 reasoning；"
            "本系统仅保存推演记录供人工审批，不会自动执行任何处置。"
        )

    parts.append(
        "\n完成调查后，必须调用 submit_conclusion 提交结构化结论。"
        "调查过程中优先调用 query_entity_graph 建立实体关联，"
        "并调用 query_asset、query_history_alerts、query_threat_intel 收集证据。"
        "提交结论时需填写 hypotheses_evaluated 与 refutation_summary。"
    )
    return "\n".join(parts)


def _render_hypothesis_template(template: dict) -> list[str]:
    lines: list[str] = []
    intent = template.get("investigation_intent")
    if intent:
        lines.append(f"调查意图: {intent}")
    for label, key in [("待验证假设", "default_hypotheses"), ("支持性线索", "supporting_hints"), ("反证线索", "refuting_hints")]:
        items = template.get(key) or []
        if not items:
            continue
        lines.append(f"{label}:")
        for item in items:
            if key == "default_hypotheses":
                lines.append(f"  - [{item.get('id')}] {item.get('label')}")
            else:
                lines.append(
                    f"  - [{item.get('id')}] {item.get('description')} "
                    f"(skill={item.get('skill')}, weight={item.get('weight')})"
                )
    required = template.get("required_skills_before_conclude") or []
    if required:
        lines.append(f"提交结论前必须调用: {', '.join(required)}")
    return lines


def build_user_prompt(ctx: InvestigationContext) -> str:
    event = ctx.event
    lines = [
        "## 待调查事件",
        f"- event_id: {event.id}",
        f"- title: {event.title}",
        f"- category: {event.primary_category}",
        f"- queue_priority: {event.queue_priority}",
        f"- risk_score: {event.risk_score}",
        f"- alert_count: {event.alert_count} (prompt 展示前 {len(ctx.alerts)} 条)",
        f"- time_range: {event.first_alert_at} ~ {event.last_alert_at}",
        f"- host: {event.aggregate_host_name}, user: {event.aggregate_user_name}",
        "",
        "## 关联告警摘要",
        "| occurred_at | rule | severity | src_ip | location | user | host | url | triage_score | route |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for alert in ctx.alerts:
        lines.append(
            f"| {alert.occurred_at} | {alert.rule_name or alert.rule_id} | {alert.severity} | "
            f"{alert.src_ip} | {alert.src_geo or '-'} | {alert.user_name} | {alert.host_name} | "
            f"{alert.request_url or '-'} | {alert.triage_rule_score} | {alert.triage_route} |"
        )
    lines.append("\n请优先调用 query_entity_graph 建立实体关联，再收集证据并调用 submit_conclusion。")
    if ctx.disposition_simulation_enabled:
        lines.append(
            "若结论将包含封禁/隔离/禁用等高影响处置建议，请先调用 simulate_disposition 再提交结论。"
        )
    return "\n".join(lines)


def build_initial_messages(ctx: InvestigationContext) -> list[dict]:
    return [
        {"role": "system", "content": build_system_prompt(ctx)},
        {"role": "user", "content": build_user_prompt(ctx)},
    ]
