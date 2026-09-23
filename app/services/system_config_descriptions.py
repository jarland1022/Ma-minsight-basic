"""Chinese descriptions for system_config keys (Settings console)."""

from __future__ import annotations

CONFIG_DESCRIPTIONS_ZH: dict[str, str] = {
    # Ingestion
    "ingestion.poll_interval_minutes": "告警采集调度间隔（分钟）",
    # Triage
    "triage.dedup_window_minutes": "去重滑动窗口（分钟）",
    "triage.deep_review_threshold": "进入深度调查队列的有效分阈值",
    "triage.low_risk_threshold": "低于该分数的告警可归档为低风险",
    "triage.uncertain_band_low": "不确定分数区间下限",
    "triage.uncertain_band_high": "不确定分数区间上限",
    "triage.sample_audit_rate": "低风险归档告警的随机抽检比例",
    "triage.llm_assist_enabled": "是否启用初筛 LLM 辅助打分",
    "triage.llm_weight": "LLM 分数在初筛有效分中的权重",
    "triage.batch_size": "每次初筛处理的最大 NEW 告警数",
    "triage.poll_interval_minutes": "初筛调度间隔（分钟）",
    "triage.category_risk": "告警类别静态风险权重表",
    # Event aggregation
    "event.aggregation_window_hours": "事件聚合时间窗口（小时，UTC 对齐）",
    "event.aggregation_batch_size": "每次聚合处理的最大告警数",
    "event.aggregation_poll_interval_minutes": "事件聚合调度间隔（分钟）",
    "event.unknown_host_sentinel": "主机名缺失时使用的占位符",
    "event.unknown_user_sentinel": "用户名缺失时使用的占位符",
    # Investigation
    "investigation.poll_interval_minutes": "Agent 深度调查调度间隔（分钟）",
    "investigation.batch_size": "每次调查的最大 Event 数",
    "investigation.max_steps": "单次调查最大 ReAct 步数",
    "investigation.max_skill_calls": "单次调查最大 Skill 调用次数",
    "investigation.daily_event_budget": "每日深度调查 Event 预算上限",
    "investigation.model_name": "调查默认 LLM 模型名",
    "investigation.reasoner_enabled": "预留：是否启用推理模型复跑",
    "investigation.alert_prompt_limit": "注入调查 Prompt 的最大告警条数",
    # Human review
    "human_review.enabled": "是否启用 IM 人工协查下发",
    "human_review.channel": "协查 IM 通道类型（如 wecom）",
    "human_review.poll_interval_minutes": "协查调度间隔（分钟）",
    "human_review.batch_size": "每次下发的最大协查请求数",
    "human_review.timeout_hours": "协查请求超时（小时）",
    "human_review.max_resend": "超时后每个事件最大重发次数",
    "human_review.reinvestigation_enabled": "人工回复后是否重新运行 Agent",
    "human_review.reinvestigation_counts_budget": "复调查是否计入每日调查预算",
    "human_review.wecom_to_user": "企业微信接收人 userid",
    "human_review.message_max_chars": "协查 outbound 消息最大字符数",
    "audit_sample.enabled": "是否生成环上审计抽检样本",
    "audit_sample.notify_via_im": "是否通过 IM 推送审计样本",
    "audit_sample.auto_confirm_whitelist": "审计样本误报是否自动确认白名单",
    # Defense assets
    "defense_assets.enabled": "是否启用防御资产沉淀流水线",
    "defense_assets.poll_interval_minutes": "防御资产沉淀调度间隔（分钟）",
    "defense_assets.batch_size": "每次沉淀的最大 Event 数",
    "defense_assets.auto_close_event": "写入判例后是否自动关闭 Event",
    "defense_assets.require_disposition_confirm": "关闭 Event 前是否需确认处置建议",
    "defense_assets.whitelist_promotion_threshold": "白名单候选升格为 active 规则所需确认次数",
    "defense_assets.whitelist_rule_ttl_days": "升格白名单规则有效天数",
    "defense_assets.create_whitelist_on_fp_only": "仅为误报裁决创建白名单候选",
    "defense_assets.embedding_enabled": "是否为判例计算向量 embedding",
    "defense_assets.embedding_search_enabled": "调查 Prompt 是否启用 embedding 检索",
    "defense_assets.embedding_model": "Embedding 模型名称",
    # Console
    "console.session_expire_hours": "控制台 JWT 会话过期时间（小时）",
    "console.page_size_default": "列表默认分页大小",
    # Eval / health check
    "eval.regression_enabled": "是否启用回归测试运行器",
    "eval.regression_use_real_llm_default": "回归测试默认是否使用真实 LLM",
    "eval.regression_cron": "回归测试 cron 表达式（null 表示禁用）",
    "eval.health_check_enabled": "是否启用链路健康探针",
    "eval.health_check_cron": "健康探针 cron 表达式（null 表示禁用）",
    "eval.health_check_agent_mock_verdict": "健康探针 Agent 阶段的模拟裁决",
    "eval.probe_retention_days": "探针告警/事件保留天数",
    # Entity graph
    "entity.graph_enabled": "是否启用实体关系图 Skill",
    "entity.graph_max_hops": "实体图 BFS 最大跳数",
    "entity.graph_max_nodes": "实体图单次返回节点上限",
    "entity.relation_ttl_days": "实体关系默认有效天数",
    # Investigation phase 2
    "investigation.hypothesis_template_enabled": "是否注入结构化假设 SOP",
    "investigation.require_refutation_attempt": "攻击确认前是否必须尝试反证",
    "investigation.min_refuting_hints_checked": "至少评估的反证线索数",
    "investigation.closure_enabled": "是否启用外置证据闭合度校验",
    "investigation.min_evidence_closure_score": "最低证据闭合度分数",
    "investigation.min_refutation_coverage_for_attack": "攻击确认最低反证覆盖率",
    "investigation.max_closure_retries": "闭合度驳回后最大补查次数",
    "investigation.supervisor_enabled": "是否启用调查监督审计",
    "investigation.supervisor_block_on_fail": "监督失败是否强制转人工",
    "investigation.metrics_enabled": "仪表盘是否展示调查成本指标",
    "investigation.target_tokens_per_event": "单 Event 调查 Token 参考上限",
    "investigation.correlation_window_hours": "告警关联扩线窗口（小时）",
    "triage.llm_assist_route_filter": "仅对这些路由启用初筛 LLM",
    "triage.llm_assist_max_per_run": "每轮初筛 LLM 辅助上限",
    "eval.require_closure_pass_for_regression": "回归测试是否校验闭合度",
    # Disposition simulation
    "disposition.simulation_enabled": "是否启用处置推演 Skill（只读模拟，不自动执行）",
    "disposition.require_approval": "推演结果是否需 Web 审批",
    "disposition.allowed_action_types": "允许推演的处置动作类型",
    "eval.entity_graph_mock_fixtures": "回归测试用实体关系图 fixture",
    "investigation.auto_raise_priority_on_correlation": "发现关联 Event 时提高 queue_priority",
    # Tool gateway
    "tools.gateway_enabled": "是否启用统一工具网关",
    "tools.gateway_timeout_seconds": "工具网关 HTTP 超时（秒）",
    "tools.gateway_audit_all_calls": "是否审计所有网关调用",
}


def description_zh(key: str, fallback: str | None = None) -> str | None:
    """Return Chinese description for a config key, or fallback."""
    return CONFIG_DESCRIPTIONS_ZH.get(key, fallback)
