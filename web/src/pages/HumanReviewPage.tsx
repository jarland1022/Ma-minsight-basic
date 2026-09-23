import { Alert, Button, Card, Input, Space, Typography, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import UserGuidePanel from "../components/UserGuidePanel";
import { PAGE_GUIDES } from "../content/userGuide";

type HumanReviewRequestRow = {
  id: string;
  event_id: string;
  question: string;
  sent_at?: string | null;
};

export default function HumanReviewPage() {
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
      message.success("已提交。AI 将在数分钟内复跑并更新事件结论，请到「事件队列 → 已结论」查看。");
      setReplies((prev) => {
        const next = { ...prev };
        delete next[variables.request_id];
        return next;
      });
      qc.invalidateQueries({ queryKey: ["pending"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: () => {
      message.error("提交失败，请检查回复内容后重试");
    },
  });

  const requests: HumanReviewRequestRow[] = data?.human_review_requests ?? [];
  const guide = PAGE_GUIDES.humanReview;

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <UserGuidePanel guide={guide} defaultExpanded />

      <Card title="待协查 Inbox">
        {!requests.length && (
          <Alert
            type="info"
            showIcon
            message="暂无待协查单"
            description={
              <>
                若仪表盘「协查中」大于 0，请管理员到{" "}
                <Link to="/settings">设置 → 手动运行 → 协查派发</Link> 执行一次。
                更多说明见 <Link to="/guide">使用指南</Link>。
              </>
            }
          />
        )}

        {requests.map((item) => {
          const shortCode = item.id.replace(/-/g, "").slice(0, 8).toLowerCase();
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
                    AI 想了解的问题
                  </Typography.Text>
                  <Typography.Text strong style={{ whiteSpace: "normal", wordBreak: "break-word" }}>
                    {item.question}
                  </Typography.Text>
                </Space>
              }
              extra={<Link to={`/events/${item.event_id}`}>查看事件详情</Link>}
            >
              {isSystemError && (
                <Alert
                  type="warning"
                  showIcon
                  style={{ marginBottom: 12 }}
                  message="这是系统配置问题，不是告警内容"
                  description="协查问题中出现 LLM 404 等字样时，请联系管理员检查 DEEPSEEK 配置并重跑 Agent 调查。您仍可先用白话描述业务情况，但根因需先修复 AI 服务。"
                />
              )}

              <Space direction="vertical" style={{ width: "100%" }} size="middle">
                <Alert
                  type="success"
                  showIcon
                  message="怎么写回复？"
                  description={
                    <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
                      <li>用日常语言即可，例如：「这是公司扫描器」「该账号是运维同事的正常操作」。</li>
                      <li>尽量包含：谁、什么系统、是否授权、是否例行任务。</li>
                      <li>不需要判断「是不是攻击」—— AI 会根据您的说明再次分析。</li>
                    </ul>
                  }
                />

                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  协查单 {item.id}
                  {item.sent_at ? ` · 下发 ${item.sent_at.slice(0, 19).replace("T", " ")}` : ""}
                </Typography.Text>

                <Input.TextArea
                  rows={5}
                  placeholder="示例：确认误报，源 IP 10.1.2.3 是我司绿盟扫描器，当晚有例行漏洞扫描任务。"
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
                  提交回复（提交后 AI 自动复跑）
                </Button>
              </Space>
            </Card>
          );
        })}
      </Card>
    </Space>
  );
}
