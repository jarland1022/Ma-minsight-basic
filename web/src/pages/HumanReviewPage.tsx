import { Alert, Button, Card, Input, Space, Typography, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import UserGuidePanel from "../components/UserGuidePanel";
import { PAGE_GUIDES } from "../content/userGuide";
import { useI18n } from "../i18n/I18nProvider";

type HumanReviewRequestRow = {
  id: string;
  event_id: string;
  question: string;
  sent_at?: string | null;
};

export default function HumanReviewPage() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [replies, setReplies] = useState<Record<string, string>>({});

  const { data } = useQuery({
    queryKey: ["pending"],
    queryFn: async () => (await api.get("/console/pending")).data,
  });

  const reply = useMutation({
    mutationFn: async (payload: { request_id: string; raw_content: string }) =>
      api.post("/human-review/responses", payload),
    onSuccess: (_data, variables) => {
      message.success(t("humanReviewPage.submitOk"));
      setReplies((prev) => {
        const next = { ...prev };
        delete next[variables.request_id];
        return next;
      });
      qc.invalidateQueries({ queryKey: ["pending"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: () => {
      message.error(t("humanReviewPage.submitFail"));
    },
  });

  const requests: HumanReviewRequestRow[] = data?.human_review_requests ?? [];
  const guide = PAGE_GUIDES.humanReview;

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <UserGuidePanel guide={guide} defaultExpanded />

      <Card title={t("humanReviewPage.inboxTitle")}>
        {!requests.length && (
          <Alert
            type="info"
            showIcon
            message={t("humanReviewPage.emptyTitle")}
            description={
              <>
                {t("humanReviewPage.emptyBody")}{" "}
                <Link to="/settings">{t("humanReviewPage.linkSettings")}</Link> ·{" "}
                <Link to="/guide">{t("common.guide")}</Link>
              </>
            }
          />
        )}

        {requests.map((item) => {
          const replyText = replies[item.id] ?? "";
          const isSystemError = /LLM error|404 Not Found|自动调查未完成/i.test(item.question);

          return (
            <Card
              key={item.id}
              size="small"
              style={{ marginBottom: 16 }}
              title={
                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {t("humanReviewPage.aiQuestion")}
                  </Typography.Text>
                  <Typography.Text strong style={{ whiteSpace: "normal", wordBreak: "break-word" }}>
                    {item.question}
                  </Typography.Text>
                </Space>
              }
              extra={<Link to={`/events/${item.event_id}`}>{t("humanReviewPage.viewEvent")}</Link>}
            >
              {isSystemError && (
                <Alert
                  type="warning"
                  showIcon
                  style={{ marginBottom: 12 }}
                  message={t("humanReviewPage.systemErrorTitle")}
                  description={t("humanReviewPage.systemErrorBody")}
                />
              )}

              <Space direction="vertical" style={{ width: "100%" }} size="middle">
                <Alert
                  type="success"
                  showIcon
                  message={t("humanReviewPage.howTitle")}
                  description={
                    <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
                      <li>{t("humanReviewPage.how1")}</li>
                      <li>{t("humanReviewPage.how2")}</li>
                      <li>{t("humanReviewPage.how3")}</li>
                    </ul>
                  }
                />

                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {t("humanReviewPage.requestMeta", { id: item.id })}
                  {item.sent_at
                    ? t("humanReviewPage.sentAt", {
                        time: item.sent_at.slice(0, 19).replace("T", " "),
                      })
                    : ""}
                </Typography.Text>

                <Input.TextArea
                  rows={5}
                  placeholder={t("humanReviewPage.placeholder")}
                  value={replyText}
                  onChange={(e) =>
                    setReplies((prev) => ({ ...prev, [item.id]: e.target.value }))
                  }
                />

                <Button
                  type="primary"
                  disabled={!replyText.trim()}
                  loading={reply.isPending && reply.variables?.request_id === item.id}
                  onClick={() =>
                    reply.mutate({ request_id: item.id, raw_content: replyText.trim() })
                  }
                >
                  {t("humanReviewPage.submit")}
                </Button>
              </Space>
            </Card>
          );
        })}
      </Card>
    </Space>
  );
}
