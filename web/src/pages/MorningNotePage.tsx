import { Alert, Button, Card, InputNumber, Space, Tag, Typography, message } from "antd";
import { PrinterOutlined, ReloadOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";

type MorningNote = {
  generated_at: string;
  timezone_label: string;
  window: { start: string; end: string; hours: number };
  snapshot: {
    ingested_alerts: number;
    auto_archived: number;
    queued_investigating: number;
    worth_opening: number;
    needs_reply: number;
    archive_breakdown: Record<string, number>;
  };
  cases: Array<{
    event_id: string;
    title: string;
    status: string | null;
    risk_score: number;
    queue_priority: number;
    alert_count: number;
    host: string | null;
    user: string | null;
    category: string | null;
    verdict: string | null;
    verdict_tag: string;
    confidence: number | null;
    evidence_closure_score: number | null;
    reasoning: string | null;
    recommended_action: string | null;
    human_question: string | null;
    investigation_id: string | null;
    investigation_status: string | null;
  }>;
  human_reviews: Array<{
    request_id: string;
    event_id: string;
    event_title: string;
    question: string;
    sent_at: string | null;
  }>;
  boundaries: string[];
};

function fmt(iso: string | null | undefined): string {
  if (!iso) return "—";
  return iso.replace("T", " ").replace("Z", " UTC");
}

function verdictColor(tag: string): string {
  if (tag === "danger") return "red";
  if (tag === "ok") return "green";
  return "orange";
}

export default function MorningNotePage() {
  const { t } = useI18n();
  const [hours, setHours] = useState(15);

  const { data, isLoading, isFetching, refetch, isError } = useQuery<MorningNote>({
    queryKey: ["morning-note", hours],
    queryFn: async () =>
      (
        await api.get("/morning-note", {
          params: { hours, timezone_label: "UTC" },
        })
      ).data,
  });

  const onPrint = () => {
    window.print();
  };

  const onRefresh = async () => {
    try {
      await refetch();
    } catch {
      message.error(t("morningNote.loadFailed"));
    }
  };

  const snap = data?.snapshot;

  return (
    <div className="ms-morning-note">
      <div className="ms-morning-toolbar no-print">
        <Space wrap>
          <Typography.Text>{t("morningNote.hours")}</Typography.Text>
          <InputNumber min={1} max={168} value={hours} onChange={(v) => setHours(Number(v) || 15)} />
          <Button icon={<ReloadOutlined />} loading={isFetching} onClick={onRefresh}>
            {t("morningNote.refresh")}
          </Button>
          <Button type="primary" icon={<PrinterOutlined />} onClick={onPrint}>
            {t("morningNote.print")}
          </Button>
        </Space>
      </div>

      <Card loading={isLoading} bordered={false} className="ms-morning-card">
        <Typography.Title level={3} style={{ marginTop: 0, color: "#0b4f8a" }}>
          {t("morningNote.title")}
        </Typography.Title>
        <Typography.Paragraph type="secondary">{t("morningNote.subtitle")}</Typography.Paragraph>

        {isError && <Alert type="error" showIcon message={t("morningNote.loadFailed")} />}

        {data && (
          <>
            <div className="ms-morning-meta">
              {t("morningNote.window")}: <strong>{fmt(data.window.start)}</strong> →{" "}
              <strong>{fmt(data.window.end)}</strong> ({data.window.hours}h · {data.timezone_label})
              <br />
              {t("morningNote.generated")}: {fmt(data.generated_at)}
            </div>

            <Alert type="info" showIcon style={{ marginBottom: 16 }} message={t("morningNote.banner")} />

            <Typography.Title level={5}>{t("morningNote.snapshot")}</Typography.Title>
            <div className="ms-morning-stats">
              <div>
                <div className="num">{snap?.ingested_alerts ?? 0}</div>
                <div className="label">{t("morningNote.ingested")}</div>
              </div>
              <div>
                <div className="num">{snap?.auto_archived ?? 0}</div>
                <div className="label">{t("morningNote.archived")}</div>
              </div>
              <div>
                <div className="num">{snap?.queued_investigating ?? 0}</div>
                <div className="label">{t("morningNote.queued")}</div>
              </div>
              <div>
                <div className="num">{snap?.worth_opening ?? 0}</div>
                <div className="label">{t("morningNote.worth")}</div>
              </div>
              <div>
                <div className="num">{snap?.needs_reply ?? 0}</div>
                <div className="label">{t("morningNote.needsReply")}</div>
              </div>
            </div>

            {snap && Object.keys(snap.archive_breakdown || {}).length > 0 && (
              <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
                {t("morningNote.archiveBreakdown")}:{" "}
                {Object.entries(snap.archive_breakdown)
                  .map(([k, v]) => `${k} ${v}`)
                  .join(" · ")}
              </Typography.Paragraph>
            )}

            <Typography.Title level={5}>{t("morningNote.cases")}</Typography.Title>
            {(data.cases || []).length === 0 ? (
              <Typography.Paragraph type="secondary">{t("morningNote.noCases")}</Typography.Paragraph>
            ) : (
              data.cases.map((c) => (
                <div key={c.event_id} className="ms-morning-case">
                  <Space wrap size={6}>
                    {c.status && (
                      <Tag title="Event status">
                        {t("eventDetail.eventStatus")}: {c.status}
                      </Tag>
                    )}
                    {c.investigation_status && (
                      <Tag title="Investigation status">
                        {t("eventDetail.investigationStatus")}: {c.investigation_status}
                      </Tag>
                    )}
                    {c.verdict ? (
                      <Tag color={verdictColor(c.verdict_tag)}>
                        {t("eventDetail.securityVerdict")}: {c.verdict}
                      </Tag>
                    ) : (
                      <Tag>{t("eventDetail.noSecurityVerdict")}</Tag>
                    )}
                    <Typography.Text strong>{c.title}</Typography.Text>
                  </Space>
                  <div className="ms-morning-case-meta">
                    {t("morningNote.host")}: {c.host || "—"} · {t("morningNote.user")}: {c.user || "—"} ·{" "}
                    {t("morningNote.risk")}: {c.risk_score} · {t("morningNote.priority")}:{" "}
                    {c.queue_priority}
                    {c.confidence != null && (
                      <>
                        {" "}
                        · {t("morningNote.confidence")}: {c.confidence}
                      </>
                    )}
                    {c.evidence_closure_score != null && (
                      <>
                        {" "}
                        · {t("morningNote.closure")}: {c.evidence_closure_score}
                      </>
                    )}
                  </div>
                  {c.reasoning && (
                    <Typography.Paragraph style={{ marginBottom: 6 }}>{c.reasoning}</Typography.Paragraph>
                  )}
                  {c.recommended_action && (
                    <Typography.Paragraph type="secondary" style={{ marginBottom: 6 }}>
                      {c.recommended_action}
                    </Typography.Paragraph>
                  )}
                  {c.human_question && (
                    <div className="ms-morning-q">
                      <strong>{t("morningNote.question")}:</strong> {c.human_question}
                    </div>
                  )}
                  <Space className="no-print" style={{ marginTop: 6 }}>
                    <Link to={`/events/${c.event_id}`}>{t("morningNote.openEvent")}</Link>
                    {c.investigation_id && (
                      <Link to={`/investigations/${c.investigation_id}/trace`}>
                        {t("morningNote.openTrace")}
                      </Link>
                    )}
                  </Space>
                </div>
              ))
            )}

            <Typography.Title level={5}>{t("morningNote.humanSection")}</Typography.Title>
            {(data.human_reviews || []).length === 0 ? (
              <Typography.Paragraph type="secondary">{t("morningNote.noHuman")}</Typography.Paragraph>
            ) : (
              <ul>
                {data.human_reviews.map((h) => (
                  <li key={h.request_id}>
                    <Link to={`/events/${h.event_id}`}>{h.event_title}</Link> — {h.question}
                  </li>
                ))}
              </ul>
            )}

            <Typography.Title level={5}>{t("morningNote.boundaries")}</Typography.Title>
            <ul>
              {(data.boundaries || []).map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>

            <Typography.Title level={5}>{t("morningNote.actions")}</Typography.Title>
            <ol>
              <li>
                {t("morningNote.action1")} (
                <Link to="/human-review">{t("nav.humanReview")}</Link>)
              </li>
              <li>{t("morningNote.action2")}</li>
              <li>
                {t("morningNote.action3")} (
                <Link to="/defense-assets">{t("nav.defenseAssets")}</Link>)
              </li>
            </ol>
          </>
        )}
      </Card>
    </div>
  );
}
