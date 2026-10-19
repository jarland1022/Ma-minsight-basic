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
