import { Alert, Space, Table, Tabs, Tag, Typography } from "antd";
import type { TableColumnsType, TableProps } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import UserGuidePanel from "../components/UserGuidePanel";
import { eventStatusLabel } from "../components/VerdictLabels";
import { EVENT_STATUS_GUIDE, PAGE_GUIDES } from "../content/userGuide";
import type { EventRow, Paginated } from "../types/api";

const statusTabs = [
  { key: "", label: "全部" },
  { key: "pending_review", label: "待调查" },
  { key: "human_pending", label: "协查中" },
  { key: "concluded", label: "已结论" },
  { key: "closed", label: "已关闭" },
];

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
      title: "事件",
      dataIndex: "title",
      render: (v, row) => <Link to={`/events/${row.id}`}>{v || row.id}</Link>,
    },
    {
      title: "状态",
      dataIndex: "status",
      render: (v, row) => (
        <Space size={4} wrap>
          <Tag color={v === "human_pending" ? "orange" : undefined} title={EVENT_STATUS_GUIDE[v]}>
            {eventStatusLabel(v)}
          </Tag>
          {v === "human_pending" && row.human_review_dispatched === false && (
            <Tag color="default">待派发</Tag>
          )}
          {v === "human_pending" && row.human_review_is_system_error && (
            <Tag color="red">系统异常</Tag>
          )}
        </Space>
      ),
    },
    {
      title: "风险",
      dataIndex: "risk_score",
      key: "risk_score",
      sorter: true,
      sortOrder: toAntSortOrder(sortBy, "risk_score", sortOrder),
    },
    {
      title: "优先级",
      dataIndex: "queue_priority",
      key: "queue_priority",
      sorter: true,
      sortOrder: toAntSortOrder(sortBy, "queue_priority", sortOrder),
    },
    { title: "告警数", dataIndex: "alert_count" },
    ...(showHumanReviewMeta
      ? [
          {
            title: "最近调查",
            dataIndex: "investigation_finished_at",
            key: "investigation_finished_at",
            sorter: true,
            sortOrder: toAntSortOrder(sortBy, "investigation_finished_at", sortOrder),
            render: (v: string | null | undefined) => formatDateTime(v),
          },
          {
            title: "协查下发",
            dataIndex: "human_review_sent_at",
            key: "human_review_sent_at",
            sorter: true,
            sortOrder: toAntSortOrder(sortBy, "human_review_sent_at", sortOrder),
            render: (v: string | null | undefined) => formatDateTime(v),
          },
          {
            title: "协查问题",
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
            title: "结论时间",
            dataIndex: "concluded_at",
            key: "concluded_at",
            sorter: true,
            sortOrder: toAntSortOrder(sortBy, "concluded_at", sortOrder),
            render: (v: string | null | undefined) => formatDateTime(v),
          },
        ]
      : []),
    { title: "主机", dataIndex: "aggregate_host_name" },
    { title: "用户", dataIndex: "aggregate_user_name" },
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
  return (
    <>
      <UserGuidePanel guide={PAGE_GUIDES.events} />
      {statusTabs.find((t) => t.key === "human_pending") && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="「协查中」事件需要您处理"
          description={
            <>
              请打开左侧 <Link to="/human-review">人工协查</Link> 用白话回复 AI 的问题；无需安全专业背景。
              详细说明见 <Link to="/guide">使用指南</Link>。
            </>
          }
        />
      )}
      <Tabs
        items={statusTabs.map((t) => ({
          key: t.key || "all",
          label: (
            <span title={t.key ? EVENT_STATUS_GUIDE[t.key] : undefined}>
              {t.label}
              {t.key === "human_pending" ? " ★" : ""}
            </span>
          ),
          children: (
            <>
              {t.key === "human_pending" && (
                <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
                  默认按「协查下发」时间从新到旧排列；「待派发」表示尚未进入人工协查 Inbox。
                  协查下发时间越新，越可能是 Agent 复跑后新产生的协查。
                </Typography.Paragraph>
              )}
              {t.key && t.key !== "human_pending" && EVENT_STATUS_GUIDE[t.key] && (
                <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
                  {EVENT_STATUS_GUIDE[t.key]}
                </Typography.Paragraph>
              )}
              <EventsTable key={t.key || "all"} status={t.key} />
            </>
          ),
        }))}
      />
    </>
  );
}
