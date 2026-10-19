# -*- coding: utf-8 -*-
"""Expand i18n catalogs and wire Events / Playbooks / Settings / ManualRun / VerdictLabels."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(r"D:\AI\Ma-minsight-basic")

EN_EXTRA = r'''
  events: {
    tabAll: "All",
    tabPending: "Pending review",
    tabHuman: "Human review",
    tabConcluded: "Concluded",
    tabClosed: "Closed",
    colEvent: "Event",
    colStatus: "Status",
    colRisk: "Risk",
    colPriority: "Priority",
    colAlerts: "Alerts",
    colLastInvestigation: "Last investigation",
    colHumanSent: "Review sent",
    colHumanQuestion: "Review question",
    colConcludedAt: "Concluded at",
    colHost: "Host",
    colUser: "User",
    tagAwaitDispatch: "Awaiting dispatch",
    tagSystemError: "System error",
    humanAlertTitle: "Events in human review need your input",
    humanAlertBody: "Open Human review and reply in plain language. See the User guide for examples.",
    status: {
      pending_review: "Pending review",
      investigating: "Investigating",
      human_pending: "Human review",
      concluded: "Concluded",
      closed: "Closed",
    },
  },
  playbooks: {
    title: "Playbooks / investigation skills",
    intro:
      "Curated defensive investigation playbooks. Matched by alert category at investigation time; browse coverage and ATT&CK mapping here.",
    totalLine: "Total {{total}} (curated {{curated}} / community {{community}})",
    attackTech: "ATT&CK techniques {{count}}",
    packPlaceholder: "Pack",
    packCurated: "Curated",
    packCommunity: "Community pack",
    domainPlaceholder: "Domain",
    categoryPlaceholder: "Alert category",
    searchPlaceholder: "Search name / ATT&CK",
    coverageTitle: "ATT&CK coverage",
    coverageStats: "Covered {{tech}} parent techniques · {{books}} playbooks",
    filterTag: "Filter {{id}}",
    clickHint: "Click a technique ID to filter the list",
    noCoverage: "No coverage",
    playbookCount: "{{id}}: {{count}} playbooks",
    density: "Playbook link density",
    densityLow: "Low",
    densityMid: "Mid",
    densityHigh: "High",
    listTitle: "Playbook list",
    listTitleFiltered: "Playbooks · {{id}}",
    colName: "Name",
    colPack: "Pack",
    colDomain: "Domain",
    colCategory: "Category",
    tagCommunity: "Community",
    tagCurated: "Curated",
    detailTitle: "Playbook detail",
    selectHint: "Select a playbook on the left",
    bindCategories: "Bound categories",
    steps: "Investigation steps",
    humanQuestions: "Sample human questions",
    upstreamSkill: "Upstream skill: {{skill}}",
  },
  settings: {
    ingestDiag: "Ingestion diagnostics",
    manualRun: "Run pipelines manually (admin)",
    sopTitle: "Investigation SOP templates (read-only)",
    sopHint: "Hypothesis templates and recommended skills for checking Agent strategy.",
    recommendedSkills: "Recommended skills: {{skills}}",
    noHypothesis: "No hypothesis_template",
    systemConfig: "System configuration",
    colKey: "Key",
    colValue: "Value",
    colDesc: "Description",
    configUpdated: "Configuration updated",
    invalidJson: "Invalid JSON",
  },
  manual: {
    expected: "Expected effect",
    where: "Where to look",
    lastRun: "Last run: {{time}}",
    never: "Never",
    runNow: "Run now",
    needAdmin: "Current account is not admin",
    needAdminBody: "Manual pipelines require an admin account (default admin). Sign out and sign back in as admin.",
    helpTitle: "About manual runs",
    helpBody:
      "Schedulers run every few minutes automatically. Use this panel to run one round now (default limit 10 per stage).",
    mainFlow: "Main flow",
    evalFlow: "Eval (Pro)",
    submitted: "Submitted",
    lockBusy: "Scheduler lock busy — retry in a few minutes",
    budgetDone: "Daily investigation budget exhausted",
    notConfigured: "Review channel not configured — skipped",
    disabled: "Feature disabled (see system config)",
    done: "Done",
    ingestZero: "Fetched 0 (no new alerts — check ingestion diagnostics)",
    ingestResult: "Fetched {{fetched}}, inserted {{inserted}}, duplicates {{dup}}",
    processed: "Processed {{n}}",
    aggResult: "Processed {{n}}, created {{created}}, merged {{merged}}",
    invResult: "Investigated {{n}} events",
    hrResult: "Dispatched {{d}}, expired {{e}}",
    defResult: "Processed {{n}} events",
    passResult: "Passed {{passed}}/{{total}}",
    ingestionSummary: "Pull new alerts from Wazuh Indexer",
    ingestionDetail: "Incremental sync into the alerts table using source cursors.",
    ingestionEffect: "NEW alert count rises; ingest pipeline timestamp updates",
    ingestionWhere: "Dashboard → NEW alerts",
    triageSummary: "Score NEW alerts and route them",
    triageDetail: "Rules, profiles, allowlists → TRIAGED or ARCHIVED.",
    triageEffect: "NEW decreases; alerts ready to aggregate",
    triageWhere: "Dashboard → alert status",
    aggregationSummary: "Merge alerts into investigation Events",
    aggregationDetail: "Host + user + category + 24h window.",
    aggregationEffect: "Pending-review Event count rises",
    aggregationWhere: "Events (pending review)",
    investigationSummary: "AI deep investigation (requires Pro License)",
    investigationDetail: "LLM + skills → structured conclusion. Community returns 402.",
    investigationEffect: "ReAct trail on event detail",
    investigationWhere: "Event detail → ReAct",
    human_reviewSummary: "Dispatch human-review questions (Pro)",
    human_reviewDetail: "WeCom push or web inbox.",
    human_reviewEffect: "Items appear on Human review",
    human_reviewWhere: "Human review",
    defense_assetsSummary: "Persist judgments and suggestions (Pro)",
    defense_assetsDetail: "Cases, allowlist candidates, disposition suggestions.",
    defense_assetsEffect: "Items on Defense assets",
    defense_assetsWhere: "Defense assets",
    regressionSummary: "Validate Agent with fixtures (Pro)",
    regressionDetail: "Not part of daily alert handling.",
    regressionEffect: "Eval page pass rate",
    regressionWhere: "Eval",
    health_checkSummary: "End-to-end probe (Pro)",
    health_checkDetail: "Synthetic alert through the pipeline.",
    health_checkEffect: "Eval PASS / FAIL",
    health_checkWhere: "Eval",
  },
'''

ZH_EXTRA = r'''
  events: {
    tabAll: "全部",
    tabPending: "待调查",
    tabHuman: "协查中",
    tabConcluded: "已结论",
    tabClosed: "已关闭",
    colEvent: "事件",
    colStatus: "状态",
    colRisk: "风险",
    colPriority: "优先级",
    colAlerts: "告警数",
    colLastInvestigation: "最近调查",
    colHumanSent: "协查下发",
    colHumanQuestion: "协查问题",
    colConcludedAt: "结论时间",
    colHost: "主机",
    colUser: "用户",
    tagAwaitDispatch: "待派发",
    tagSystemError: "系统异常",
    humanAlertTitle: "「协查中」事件需要您处理",
    humanAlertBody: "请打开人工协查用白话回复；详见使用指南。",
    status: {
      pending_review: "待调查",
      investigating: "调查中",
      human_pending: "协查中",
      concluded: "已结论",
      closed: "已关闭",
    },
  },
  playbooks: {
    title: "技能库 / 调查剧本",
    intro:
      "精选防御向调查剧本。调查时会按告警类别自动注入 Agent 提示词；这里展示覆盖场景与 ATT&CK 映射。",
    totalLine: "共 {{total}} 条（核心 {{curated}} / 社区防御子集 {{community}}）",
    attackTech: "ATT&CK 技术 {{count}}",
    packPlaceholder: "来源包",
    packCurated: "核心剧本",
    packCommunity: "社区防御子集",
    domainPlaceholder: "领域",
    categoryPlaceholder: "告警类别",
    searchPlaceholder: "搜索名称 / ATT&CK",
    coverageTitle: "ATT&CK 覆盖看板",
    coverageStats: "覆盖 {{tech}} 个父技术 · {{books}} 条剧本",
    filterTag: "筛选 {{id}}",
    clickHint: "点击技术 ID 筛选下方列表",
    noCoverage: "暂无覆盖",
    playbookCount: "{{id}}: {{count}} 条剧本",
    density: "剧本关联密度",
    densityLow: "低",
    densityMid: "中",
    densityHigh: "高",
    listTitle: "剧本列表",
    listTitleFiltered: "剧本列表 · {{id}}",
    colName: "名称",
    colPack: "来源",
    colDomain: "领域",
    colCategory: "类别",
    tagCommunity: "社区",
    tagCurated: "核心",
    detailTitle: "剧本详情",
    selectHint: "选择左侧剧本查看详情",
    bindCategories: "绑定类别",
    steps: "调查要点",
    humanQuestions: "协查问题示例",
    upstreamSkill: "上游 skill: {{skill}}",
  },
  settings: {
    ingestDiag: "告警入库故障排查",
    manualRun: "手动运行流水线（管理员）",
    sopTitle: "调查 SOP 模板（只读）",
    sopHint: "结构化假设模板与推荐 Skill，供运维核对 Agent 调查策略。",
    recommendedSkills: "推荐 Skill：{{skills}}",
    noHypothesis: "无 hypothesis_template",
    systemConfig: "系统配置",
    colKey: "配置项",
    colValue: "值",
    colDesc: "说明",
    configUpdated: "配置已更新",
    invalidJson: "JSON 格式无效",
  },
  manual: {
    expected: "预期效果",
    where: "查看位置",
    lastRun: "最近运行：{{time}}",
    never: "从未运行",
    runNow: "立即运行",
    needAdmin: "当前账号无管理员权限",
    needAdminBody: "手动运行流水线需要管理员账号（默认 admin）。请退出后使用管理员重新登录。",
    helpTitle: "手动运行说明",
    helpBody: "系统会自动调度各阶段；此处用于立即补跑一轮（默认每轮最多 10 条）。",
    mainFlow: "主流程",
    evalFlow: "评测（Pro）",
    submitted: "已提交",
    lockBusy: "调度锁占用，本轮未执行（约 2–5 分钟后重试）",
    budgetDone: "今日调查预算已用完",
    notConfigured: "协查通道未配置，已跳过",
    disabled: "功能已关闭（见系统配置）",
    done: "已完成",
    ingestZero: "拉取 0 条（暂无新告警，请查看入库故障排查）",
    ingestResult: "拉取 {{fetched}} 条，新增 {{inserted}} 条，重复 {{dup}} 条",
    processed: "处理 {{n}} 条",
    aggResult: "处理 {{n}} 条，新建 Event {{created}}，合并 {{merged}}",
    invResult: "调查 {{n}} 个 Event",
    hrResult: "下发 {{d}} 条，过期 {{e}} 条",
    defResult: "沉淀 {{n}} 个 Event",
    passResult: "通过 {{passed}}/{{total}}",
    ingestionSummary: "从 Wazuh Indexer 拉取新告警",
    ingestionDetail: "读取已启用数据源游标，增量同步到 alerts 表。",
    ingestionEffect: "NEW 告警数量上升；入库流水线时间更新",
    ingestionWhere: "运营概览 → 初筛告警（NEW）",
    triageSummary: "对 NEW 告警打分并决定路由",
    triageDetail: "规则分、画像、白名单等；结果写入 triage_results。",
    triageEffect: "NEW 减少；待聚合告警产生",
    triageWhere: "运营概览 → 告警状态分布",
    aggregationSummary: "把告警合并为调查 Event",
    aggregationDetail: "按主机+用户+类别+24h 窗口合并。",
    aggregationEffect: "「待调查 Event」数量增加",
    aggregationWhere: "事件列表（状态：待调查）",
    investigationSummary: "AI 深度调查（需专业版 License）",
    investigationDetail: "调用 LLM + Skill。社区版点击将返回 402。",
    investigationEffect: "事件详情出现 ReAct 记录",
    investigationWhere: "事件详情 → ReAct 对话流",
    human_reviewSummary: "向 IM 发送人工协查问题（需专业版）",
    human_reviewDetail: "企微推送或 Web 协查 inbox。",
    human_reviewEffect: "人工协查页出现待回复请求",
    human_reviewWhere: "协查管理",
    defense_assetsSummary: "已结论事件写入判例与建议（需专业版）",
    defense_assetsDetail: "判例、白名单候选、处置建议等。",
    defense_assetsEffect: "防御资产页出现待确认项",
    defense_assetsWhere: "防御资产",
    regressionSummary: "用内置样本校验 Agent（需专业版）",
    regressionDetail: "不参与日常告警处理。",
    regressionEffect: "评测页显示最新回归通过率",
    regressionWhere: "评测",
    health_checkSummary: "端到端自检（需专业版）",
    health_checkDetail: "模拟探针告警跑通整条链路。",
    health_checkEffect: "评测页显示 PASS / FAIL",
    health_checkWhere: "评测",
  },
'''


def inject_catalog(path: Path, extra: str) -> None:
    text = path.read_text(encoding="utf-8")
    if "events: {" in text:
        print(path.name, "already has events")
        return
    # insert before final common/pipelines closing — replace trailing pipelines block end
    marker = "  pipelines: {"
    idx = text.find(marker)
    if idx < 0:
        raise SystemExit(f"no pipelines in {path}")
    # find end of file export
    end = text.rfind("};\n\nexport default")
    if end < 0:
        end = text.rfind("};\r\n\r\nexport default")
    if end < 0:
        raise SystemExit(f"no export in {path}")
    # Keep pipelines section, append extras before closing `};` of root object
    # Actually insert after pipelines block
    close_pipelines = text.find("  },\n};", idx)
    if close_pipelines < 0:
        close_pipelines = text.find("  },\r\n};", idx)
    if close_pipelines < 0:
        raise SystemExit(f"no close pipelines {path}")
    insert_at = close_pipelines + len("  },")
    new_text = text[:insert_at] + "\n" + extra.rstrip() + "\n" + text[insert_at:]
    path.write_text(new_text, encoding="utf-8")
    print("catalog", path.name, "ok")


def write_events_page() -> None:
    path = ROOT / "web/src/pages/EventsPage.tsx"
    path.write_text(
        r'''import { Alert, Space, Table, Tabs, Tag, Typography } from "antd";
import type { TableColumnsType, TableProps } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import UserGuidePanel from "../components/UserGuidePanel";
import { eventStatusLabel } from "../components/VerdictLabels";
import { EVENT_STATUS_GUIDE, PAGE_GUIDES } from "../content/userGuide";
import type { EventRow, Paginated } from "../types/api";
import { useI18n } from "../i18n/I18nProvider";

function formatDateTime(iso: string | null | undefined): string {
  return iso ? iso.slice(0, 19).replace("T", " ") : "—";
}

type EventSortBy =
  | "concluded_at"
  | "investigation_finished_at"
  | "human_review_sent_at"
  | "risk_score"
  | "queue_priority"
  | "last_alert_at";
type EventSortOrder = "asc" | "desc";
type AntSortOrder = "ascend" | "descend" | undefined;

function isSystemReviewQuestion(question: string | null | undefined): boolean {
  return Boolean(question && /LLM error|404 Not Found|自动调查未完成/i.test(question));
}

function toAntSortOrder(
  active: EventSortBy | undefined,
  column: EventSortBy,
  order: EventSortOrder,
): AntSortOrder {
  if (active !== column) {
    return undefined;
  }
  return order === "asc" ? "ascend" : "descend";
}

function defaultSortForTab(status: string): { sortBy?: EventSortBy; sortOrder: EventSortOrder } {
  if (status === "concluded" || status === "closed") {
    return { sortBy: "concluded_at", sortOrder: "desc" };
  }
  if (status === "human_pending") {
    return { sortBy: "human_review_sent_at", sortOrder: "desc" };
  }
  return { sortOrder: "desc" };
}

function EventsTable({ status }: { status: string }) {
  const { t } = useI18n();
  const defaults = useMemo(() => defaultSortForTab(status), [status]);
  const [sortBy, setSortBy] = useState<EventSortBy | undefined>(defaults.sortBy);
  const [sortOrder, setSortOrder] = useState<EventSortOrder>(defaults.sortOrder);

  const { data, isLoading } = useQuery<Paginated<EventRow>>({
    queryKey: ["events", status, sortBy, sortOrder],
    queryFn: async () =>
      (
        await api.get("/events", {
          params: {
            status: status || undefined,
            page_size: 50,
            sort_by: sortBy,
            sort_order: sortOrder,
          },
        })
      ).data,
  });

  const showConcludedAt = status === "concluded" || status === "closed" || status === "";
  const showHumanReviewMeta = status === "human_pending";

  const handleTableChange: TableProps<EventRow>["onChange"] = (_pagination, _filters, sorter) => {
    const single = Array.isArray(sorter) ? sorter[0] : sorter;
    if (!single?.field || !single.order) {
      setSortBy(defaults.sortBy);
      setSortOrder(defaults.sortOrder);
      return;
    }
    setSortBy(String(single.field) as EventSortBy);
    setSortOrder(single.order === "ascend" ? "asc" : "desc");
  };

  const columns: TableColumnsType<EventRow> = [
    {
      title: t("events.colEvent"),
      dataIndex: "title",
      render: (v, row) => <Link to={`/events/${row.id}`}>{v || row.id}</Link>,
    },
    {
      title: t("events.colStatus"),
      dataIndex: "status",
      render: (v, row) => (
        <Space size={4} wrap>
          <Tag color={v === "human_pending" ? "orange" : undefined} title={EVENT_STATUS_GUIDE[v]}>
            {eventStatusLabel(v, t)}
          </Tag>
          {v === "human_pending" && row.human_review_dispatched === false && (
            <Tag color="default">{t("events.tagAwaitDispatch")}</Tag>
          )}
          {v === "human_pending" && row.human_review_is_system_error && (
            <Tag color="red">{t("events.tagSystemError")}</Tag>
          )}
        </Space>
      ),
    },
    {
      title: t("events.colRisk"),
      dataIndex: "risk_score",
      key: "risk_score",
      sorter: true,
      sortOrder: toAntSortOrder(sortBy, "risk_score", sortOrder),
    },
    {
      title: t("events.colPriority"),
      dataIndex: "queue_priority",
      key: "queue_priority",
      sorter: true,
      sortOrder: toAntSortOrder(sortBy, "queue_priority", sortOrder),
    },
    { title: t("events.colAlerts"), dataIndex: "alert_count" },
    ...(showHumanReviewMeta
      ? [
          {
            title: t("events.colLastInvestigation"),
            dataIndex: "investigation_finished_at",
            key: "investigation_finished_at",
            sorter: true,
            sortOrder: toAntSortOrder(sortBy, "investigation_finished_at", sortOrder),
            render: (v: string | null | undefined) => formatDateTime(v),
          },
          {
            title: t("events.colHumanSent"),
            dataIndex: "human_review_sent_at",
            key: "human_review_sent_at",
            sorter: true,
            sortOrder: toAntSortOrder(sortBy, "human_review_sent_at", sortOrder),
            render: (v: string | null | undefined) => formatDateTime(v),
          },
          {
            title: t("events.colHumanQuestion"),
            dataIndex: "human_review_question",
            ellipsis: true,
            render: (v: string | null | undefined) =>
              v ? (
                <Typography.Text
                  type={isSystemReviewQuestion(v) ? "danger" : undefined}
                  style={{ maxWidth: 280 }}
                  ellipsis={{ tooltip: v }}
                >
                  {v}
                </Typography.Text>
              ) : (
                "—"
              ),
          },
        ]
      : []),
    ...(showConcludedAt
      ? [
          {
            title: t("events.colConcludedAt"),
            dataIndex: "concluded_at",
            key: "concluded_at",
            sorter: true,
            sortOrder: toAntSortOrder(sortBy, "concluded_at", sortOrder),
            render: (v: string | null | undefined) => formatDateTime(v),
          },
        ]
      : []),
    { title: t("events.colHost"), dataIndex: "aggregate_host_name" },
    { title: t("events.colUser"), dataIndex: "aggregate_user_name" },
  ];

  return (
    <Table<EventRow>
      loading={isLoading}
      rowKey="id"
      dataSource={data?.items ?? []}
      onChange={handleTableChange}
      columns={columns}
    />
  );
}

export default function EventsPage() {
  const { t } = useI18n();
  const statusTabs = [
    { key: "", label: t("events.tabAll") },
    { key: "pending_review", label: t("events.tabPending") },
    { key: "human_pending", label: t("events.tabHuman") },
    { key: "concluded", label: t("events.tabConcluded") },
    { key: "closed", label: t("events.tabClosed") },
  ];

  return (
    <>
      <UserGuidePanel guide={PAGE_GUIDES.events} />
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
        message={t("events.humanAlertTitle")}
        description={
          <>
            {t("events.humanAlertBody")}{" "}
            <Link to="/human-review">{t("nav.humanReview")}</Link> ·{" "}
            <Link to="/guide">{t("common.guide")}</Link>
          </>
        }
      />
      <Tabs
        items={statusTabs.map((tab) => ({
          key: tab.key || "all",
          label: (
            <span title={tab.key ? EVENT_STATUS_GUIDE[tab.key] : undefined}>
              {tab.label}
              {tab.key === "human_pending" ? " ★" : ""}
            </span>
          ),
          children: <EventsTable status={tab.key} />,
        }))}
      />
    </>
  );
}
''',
        encoding="utf-8",
    )
    print("EventsPage ok")


def patch_verdict_labels() -> None:
    path = ROOT / "web/src/components/VerdictLabels.tsx"
    text = path.read_text(encoding="utf-8")
    old = '''export function eventStatusLabel(status: string | null | undefined): string {
  const map: Record<string, string> = {
    pending_review: "待调查",
    investigating: "调查中",
    human_pending: "协查中",
    concluded: "已结论",
    closed: "已关闭",
  };
  if (!status) return "—";
  return map[status] ?? status;
}'''
    new = '''export function eventStatusLabel(
  status: string | null | undefined,
  t?: (path: string) => string,
): string {
  if (!status) return "—";
  if (t) {
    const key = `events.status.${status}`;
    const labeled = t(key);
    if (labeled !== key) return labeled;
  }
  const map: Record<string, string> = {
    pending_review: "Pending review",
    investigating: "Investigating",
    human_pending: "Human review",
    concluded: "Concluded",
    closed: "Closed",
  };
  return map[status] ?? status;
}'''
    if old not in text:
        # already patched or different
        if "events.status." in text:
            print("VerdictLabels already patched")
            return
        raise SystemExit("VerdictLabels pattern missing")
    path.write_text(text.replace(old, new), encoding="utf-8")
    print("VerdictLabels ok")


def write_settings() -> None:
    (ROOT / "web/src/pages/SettingsPage.tsx").write_text(
        r'''import { Card, Space, Table, Typography, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import IngestionDiagnosticsPanel from "../components/IngestionDiagnosticsPanel";
import ManualRunPanel from "../components/ManualRunPanel";
import type { ConfigRow } from "../types/api";
import { useI18n } from "../i18n/I18nProvider";

export default function SettingsPage() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data: configs, isLoading } = useQuery<ConfigRow[]>({
    queryKey: ["config"],
    queryFn: async () => (await api.get("/system/config")).data,
  });

  const { data: sops } = useQuery({
    queryKey: ["investigation-sops"],
    queryFn: async () => (await api.get("/console/investigation-sops")).data,
  });

  const updateConfig = useMutation({
    mutationFn: (row: { key: string; value: unknown }) =>
      api.put(`/system/config/${row.key}`, { value: row.value }),
    onSuccess: () => {
      message.success(t("settings.configUpdated"));
      qc.invalidateQueries({ queryKey: ["config"] });
    },
  });

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Card title={t("settings.ingestDiag")}>
        <IngestionDiagnosticsPanel />
      </Card>

      <Card title={t("settings.manualRun")}>
        <ManualRunPanel />
      </Card>

      <Card title={t("settings.sopTitle")}>
        <Typography.Paragraph type="secondary">{t("settings.sopHint")}</Typography.Paragraph>
        {(sops?.items ?? []).map(
          (sop: {
            id: string;
            alert_category: string;
            name: string;
            recommended_skills?: string[];
            hypothesis_template?: unknown;
          }) => (
            <Card
              key={sop.id}
              size="small"
              style={{ marginBottom: 12 }}
              title={`${sop.alert_category} · ${sop.name}`}
            >
              <Typography.Text type="secondary">
                {t("settings.recommendedSkills", {
                  skills: (sop.recommended_skills ?? []).join(", ") || "—",
                })}
              </Typography.Text>
              {sop.hypothesis_template ? (
                <pre style={{ whiteSpace: "pre-wrap", marginTop: 8, fontSize: 12 }}>
                  {JSON.stringify(sop.hypothesis_template, null, 2)}
                </pre>
              ) : (
                <Typography.Text type="secondary">{t("settings.noHypothesis")}</Typography.Text>
              )}
            </Card>
          ),
        )}
      </Card>

      <Card title={t("settings.systemConfig")}>
        <Table<ConfigRow>
          loading={isLoading}
          rowKey="key"
          dataSource={configs ?? []}
          pagination={{ pageSize: 20 }}
          columns={[
            { title: t("settings.colKey"), dataIndex: "key", width: 280 },
            {
              title: t("settings.colValue"),
              dataIndex: "value",
              render: (v) => <Typography.Text code>{JSON.stringify(v)}</Typography.Text>,
            },
            { title: t("settings.colDesc"), dataIndex: "description", ellipsis: true },
          ]}
          expandable={{
            expandedRowRender: (row) => (
              <Typography.Paragraph
                editable={{
                  onChange: (text) => {
                    try {
                      updateConfig.mutate({ key: row.key, value: JSON.parse(text) });
                    } catch {
                      message.error(t("settings.invalidJson"));
                    }
                  },
                }}
              >
                {JSON.stringify(row.value, null, 2)}
              </Typography.Paragraph>
            ),
          }}
        />
      </Card>
    </Space>
  );
}
''',
        encoding="utf-8",
    )
    print("SettingsPage ok")


def main() -> None:
    inject_catalog(ROOT / "web/src/i18n/en.ts", EN_EXTRA)
    inject_catalog(ROOT / "web/src/i18n/zh.ts", ZH_EXTRA)
    write_events_page()
    patch_verdict_labels()
    write_settings()
    print("partial done — playbooks/manual via separate write")


if __name__ == "__main__":
    main()
