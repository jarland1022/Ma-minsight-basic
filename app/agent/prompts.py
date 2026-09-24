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
        "处置动作只能是建议，recommended_action 中需体现「建议」措辞；第 5 步定性与处置拍板权在人工。",
        "实体画像 memories 与判例仅供参考(reference_only)，不得直接当作放行或定罪依据。",
    ]

    parts.extend(_methodology_section())

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
        "调查过程中优先：query_behavior_timeline（行为时间线）→ query_entity_graph → "
        "query_asset / query_history_alerts / query_threat_intel；"
        "若告警含 file_hash/进程，再调用 query_sample_enrichment（样本/端点路径）。"
        "提交结论时需填写 hypotheses_evaluated、refutation_summary，"
        "并尽量填写 evidence_strength 与 disposition_grade。"
    )
    return "\n".join(parts)


def _methodology_section() -> list[str]:
    return [
        "\n## 五步研判流程（人机分工）",
        "1) 归一化摘要：调用 query_behavior_timeline，按时间整理行为线；时间戳必须可回 source_ref。",
        "2) IOC 提取比对：从时间线/告警提取 IP/域/哈希，调用 query_threat_intel；评分以 sources[] 为准。",
        "3) 样本/端点初判：有 file_hash/进程时调用 query_sample_enrichment；"
        "sandbox_available=false 时不得编造沙箱/capa/家族结论。",
        "4) 场景比对：对照剧本 ATT&CK/调查要点与历史告警模式；找不到匹配就明确说找不到。",
        "5) 结论定级：人拥有最终拍板权；你只起草建议。attack_confirmed 必须 evidence_strength=multi_path（至少两路独立证据）。",
        "\n## 四路证据交叉验证",
        "- 流量/告警行为（timeline、history_alerts）",
        "- 威胁情报（query_threat_intel 的 sources/conflicts）",
        "- 样本/端点线索（query_sample_enrichment：hash、进程；无数据则标明路径缺失）",
        "- 知识/剧本/判例（playbooks、reference_cases，仅参考）",
        "任一路对不上时回到差异点，不得多数票强行定罪。",
        "\n## 防幻觉校验清单",
        "- 时间戳、端口、哈希、IP 必须来自 Skill 返回字段，禁止顺滑改写。",
        "- 每个关键结论在 reasoning 中点明 evidence_refs / source_ref。",
        "- 情报评分、家族归属以平台缓存 sources 为准；unknown/冲突不得当作恶意铁证。",
        "- 单路孤证：evidence_strength=single_path，verdict 不得用 attack_confirmed（改 insufficient 或 needs_human_review）。",
        "- 处置（隔离/封禁/禁用）只能建议，由人工确认执行。",
        "\n## 定性与处置分级（建议）",
        "- confirmed_compromise / attack_confirmed：两路以上独立证据 + 样本或强行为链 → 建议隔离/重置凭据（需人确认）。",
        "- suspicious：单路强证据或情报冲突 → 建议封禁外连目标、持续监控、补证据。",
        "- false_positive / likely_false_positive：特征可解释 → 记录原因、建议优化规则。",
        "- needs_more_evidence / insufficient_information：证据不足 → 填写 human_query。",
    ]


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
    lines.append(
        "\n请先调用 query_behavior_timeline 生成可回源的行为时间线，"
        "再 query_entity_graph 建立关联，收集情报/资产证据后调用 submit_conclusion。"
        "attack_confirmed 须 evidence_strength=multi_path。"
    )
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
