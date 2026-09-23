import {
  Alert,
  Button,
  Card,
  Descriptions,
  Input,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { isAxiosError } from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import EventWorkspace from "../components/EventWorkspace";
import PageBackHeader from "../components/PageBackHeader";
import UserGuidePanel from "../components/UserGuidePanel";
import { VerdictTag, eventStatusLabel } from "../components/VerdictLabels";
import { PAGE_GUIDES, VERDICT_GUIDE } from "../content/userGuide";
import type { AlertDetailRow, DispositionRow, EventDetail } from "../types/api";

export default function EventDetailPage() {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const selectedAlertId = location.hash.startsWith("#alert-")
    ? location.hash.slice("#alert-".length)
    : null;

  const { data, isLoading } = useQuery<EventDetail>({
    queryKey: ["event", id],
    queryFn: async () => (await api.get(`/events/${id}`)).data,
    enabled: !!id,
  });

  const selectedAlert = data?.alert_details?.find((row) => row.alert_id === selectedAlertId);

  useEffect(() => {
    if (!selectedAlertId) {
      return;
    }
    document.getElementById(`alert-${selectedAlertId}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [selectedAlertId, data?.alert_details]);

  const [hrReply, setHrReply] = useState("");

  const pendingRequest = data?.human_reviews?.find((r: { status: string }) => r.status === "sent");

  const replyMutation = useMutation({
    mutationFn: async (raw_content: string) =>
      api.post("/human-review/responses", {
        raw_content,
        request_id: pendingRequest?.id,
      }),
    onSuccess: () => {
      message.success("协查回复已提交，AI 将自动复跑并更新结论");
      setHrReply("");
      qc.invalidateQueries({ queryKey: ["event", id] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["noisy-rules"] });
    },
  });

  const confirmDisp = useMutation({
    mutationFn: async (recordId: string) =>
      api.post(`/disposition/${recordId}/confirm`, { confirmed_action: null }),
    onSuccess: () => {
      message.success("处置已确认");
      qc.invalidateQueries({ queryKey: ["event", id] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["noisy-rules"] });
    },
    onError: (error) => {
      const detail = isAxiosError(error) ? error.response?.data?.detail : undefined;
      message.error(typeof detail === "string" ? detail : "处置确认失败，请稍后重试");
    },
  });

  const selectAlert = (alertId: string) => {
    navigate({ pathname: `/events/${id}`, hash: `alert-${alertId}` }, { replace: true });
  };

  if (isLoading || !data) {
    return <Typography.Text>加载中...</Typography.Text>;
  }

  const latestInv = data.investigations?.[0];
  const pendingDispositions = (data.dispositions ?? []).filter((d) => d.status === "suggested");
  const verdictInfo = latestInv?.conclusion?.verdict
    ? VERDICT_GUIDE[latestInv.conclusion.verdict]
    : undefined;

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <PageBackHeader to="/events" label="返回事件队列" />

      {(data.status === "human_pending" || pendingRequest) && (
        <Alert
          type="warning"
          showIcon
          message="此事件需要您补充信息"
          description="请在下方「Web 协查回复」或左侧「人工协查」用白话说明业务背景，无需判断是否为攻击。提交后 AI 会自动再次分析。"
        />
      )}

      <UserGuidePanel guide={PAGE_GUIDES.eventDetail} />

      <EventWorkspace
        alerts={data.alert_details ?? []}
        snapshot={data.entity_context_snapshot}
        investigation={latestInv}
        playbooks={data.matched_playbooks}
      />

      <Card title={data.title || data.id}>
        <Descriptions column={2}>
          <Descriptions.Item label="状态">
            <Tag color={data.status === "human_pending" ? "orange" : undefined}>
              {eventStatusLabel(data.status)}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="风险">{data.risk_score}</Descriptions.Item>
          <Descriptions.Item label="主机">{data.aggregate_host_name}</Descriptions.Item>
          <Descriptions.Item label="用户">{data.aggregate_user_name}</Descriptions.Item>
          <Descriptions.Item label="类别">{data.primary_category || data.aggregate_category}</Descriptions.Item>
          {(data.status === "concluded" || data.status === "closed") && latestInv?.finished_at && (
            <Descriptions.Item label="结论时间">
              {latestInv.finished_at.slice(0, 19).replace("T", " ")}
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      <Card title="关联告警（初筛路由 ≠ Agent 结论）">
        <Table<AlertDetailRow>
          rowKey="alert_id"
          pagination={false}
          dataSource={data.alert_details ?? []}
          rowClassName={(row) => (row.alert_id === selectedAlertId ? "ant-table-row-selected" : "")}
          onRow={(row) => ({
            onClick: () => selectAlert(row.alert_id),
            style: { cursor: "pointer" },
          })}
          columns={[
            {
              title: "规则",
              dataIndex: "rule_name",
              render: (v, row) => (
                <Typography.Link
                  onClick={(event) => {
                    event.stopPropagation();
                    selectAlert(row.alert_id);
                  }}
                >
                  {v}
                </Typography.Link>
              ),
            },
            { title: "初筛路由", dataIndex: "triage_route", render: (v) => <Tag>{v}</Tag> },
            { title: "初筛分", dataIndex: "triage_score" },
            { title: "严重度", dataIndex: "severity" },
            { title: "源 IP", dataIndex: "src_ip" },
            {
              title: "归属地",
              dataIndex: "src_geo",
              render: (value: string | null | undefined) => value || "-",
            },
          ]}
        />

        {selectedAlert && (
          <Card
            id={`alert-${selectedAlert.alert_id}`}
            size="small"
            title="告警详情"
            style={{ marginTop: 16 }}
            extra={
              <Button type="link" onClick={() => navigate({ pathname: `/events/${id}` }, { replace: true })}>
                关闭
              </Button>
            }
          >
            <Descriptions column={2} size="small">
              <Descriptions.Item label="告警 ID">{selectedAlert.alert_id}</Descriptions.Item>
              <Descriptions.Item label="发生时间">{selectedAlert.occurred_at}</Descriptions.Item>
              <Descriptions.Item label="规则">{selectedAlert.rule_name}</Descriptions.Item>
              <Descriptions.Item label="严重度">{selectedAlert.severity}</Descriptions.Item>
              <Descriptions.Item label="源 IP">{selectedAlert.src_ip || "-"}</Descriptions.Item>
              <Descriptions.Item label="归属地">{selectedAlert.src_geo || "-"}</Descriptions.Item>
              <Descriptions.Item label="主机">{selectedAlert.host_name || "-"}</Descriptions.Item>
              <Descriptions.Item label="用户">{selectedAlert.user_name || "-"}</Descriptions.Item>
              <Descriptions.Item label="URL">{selectedAlert.request_url || "-"}</Descriptions.Item>
              <Descriptions.Item label="初筛路由">
                <Tag>{selectedAlert.triage_route}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="初筛分">{selectedAlert.triage_score}</Descriptions.Item>
            </Descriptions>
          </Card>
        )}
      </Card>

      {latestInv?.conclusion && (
        <Card title="Agent 复核结论">
          <Typography.Paragraph>
            <VerdictTag verdict={latestInv.conclusion.verdict} /> 置信度{" "}
            {latestInv.conclusion.confidence}
            {latestInv.conclusion.closure_passed != null && (
              <>
                {" "}
                <Tag color={latestInv.conclusion.closure_passed ? "green" : "orange"}>
                  证据闭合 {latestInv.conclusion.closure_passed ? "通过" : "未通过"}
                </Tag>
              </>
            )}
          </Typography.Paragraph>
          {verdictInfo && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message={`结论含义：${verdictInfo.label}`}
              description={
                <>
                  {verdictInfo.meaning}
                  <br />
                  <strong>建议操作：</strong>
                  {verdictInfo.action}
                </>
              }
            />
          )}
          {(latestInv.conclusion.evidence_closure_score != null ||
            latestInv.conclusion.refutation_coverage != null) && (
            <Typography.Paragraph type="secondary">
              闭合度 {latestInv.conclusion.evidence_closure_score?.toFixed(2) ?? "—"} · 反证覆盖{" "}
              {latestInv.conclusion.refutation_coverage?.toFixed(2) ?? "—"}
              {(latestInv.closure_retry_count ?? 0) > 0 && (
                <> · 闭合驳回 {latestInv.closure_retry_count} 次</>
              )}
            </Typography.Paragraph>
          )}
          {latestInv.conclusion.refutation_summary && (
            <Typography.Paragraph>
              <Typography.Text strong>反证摘要：</Typography.Text>
              {latestInv.conclusion.refutation_summary}
            </Typography.Paragraph>
          )}
          <Typography.Paragraph>{latestInv.conclusion.reasoning}</Typography.Paragraph>
          {latestInv.conclusion.human_query && (
            <Typography.Text type="warning">协查问题：{latestInv.conclusion.human_query}</Typography.Text>
          )}
          {latestInv.conclusion.recommended_action && (
            <Typography.Paragraph style={{ marginTop: 8 }}>
              <Typography.Text strong>处置建议（结论）：</Typography.Text>
              {latestInv.conclusion.recommended_action}
            </Typography.Paragraph>
          )}
          <div style={{ marginTop: 12 }}>
            <Typography.Link onClick={() => navigate(`/investigations/${latestInv.id}/trace`)}>
              查看调查轨迹 →
            </Typography.Link>
          </div>
        </Card>
      )}

      {(latestInv?.supervisor_audits?.length ?? 0) > 0 && (
        <Card title="监督审计">
          {latestInv!.supervisor_audits!.map((audit) => (
            <div key={audit.id} style={{ marginBottom: 12 }}>
              <Tag color={audit.passed ? "green" : "red"}>{audit.passed ? "通过" : "未通过"}</Tag>
              <Typography.Text type="secondary"> {audit.audit_type}</Typography.Text>
              {Array.isArray(audit.findings?.issues) ? (
                <ul style={{ marginTop: 8, marginBottom: 0 }}>
                  {(audit.findings!.issues as string[]).map((issue) => (
                    <li key={issue}>{issue}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ))}
        </Card>
      )}

      {(latestInv?.disposition_simulations?.length ?? 0) > 0 && (
        <Card title="处置推演（只读模拟）">
          {latestInv!.disposition_simulations!.map((sim) => (
            <div key={sim.id} style={{ marginBottom: 12 }}>
              <Tag>{sim.action_type}</Tag>
              <Tag color={sim.approval_status === "approved" ? "green" : sim.approval_status === "rejected" ? "red" : "default"}>
                {sim.approval_status}
              </Tag>
              <Typography.Text type="secondary">
                {" "}
                影响主机 {sim.affected_host_count ?? "—"} · 预估中断 {sim.estimated_downtime_minutes ?? "—"} 分钟
              </Typography.Text>
              {sim.summary && (
                <Typography.Paragraph type="secondary" style={{ marginTop: 4, marginBottom: 0 }}>
                  {sim.summary}
                </Typography.Paragraph>
              )}
            </div>
          ))}
        </Card>
      )}

      {pendingRequest && (
        <Card title="Web 协查回复">
          <Alert
            type="success"
            showIcon
            style={{ marginBottom: 12 }}
            message="请回答 AI 的协查问题"
            description="用您熟悉的业务语言描述即可，例如是否内部 IP、是否例行扫描、账号是否授权操作。"
          />
          {latestInv?.conclusion?.human_query && (
            <Typography.Paragraph type="warning">
              <Typography.Text strong>AI 想了解：</Typography.Text> {latestInv.conclusion.human_query}
            </Typography.Paragraph>
          )}
          <Input.TextArea
            rows={4}
            placeholder="示例：确认误报，该 IP 为公司 WAF 健康检查，非攻击行为。"
            value={hrReply}
            onChange={(e) => setHrReply(e.target.value)}
          />
          <Button
            type="primary"
            style={{ marginTop: 8 }}
            disabled={!hrReply.trim()}
            loading={replyMutation.isPending}
            onClick={() => replyMutation.mutate(hrReply.trim())}
          >
            提交回复
          </Button>
        </Card>
      )}

      <Card title="处置建议（需人工确认，不会自动执行）">
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="「确认」仅表示您已审阅并同意记录该建议"
          description="系统不会在防火墙上自动封 IP 或隔离主机。若确需处置，请由运维在对应安全设备上操作。"
        />
        <Table<DispositionRow>
          rowKey="id"
          pagination={false}
          locale={{
            emptyText:
              latestInv?.conclusion?.recommended_action
                ? "结论中已有建议文本，但无独立处置记录（可能为历史数据）；请以上方「处置建议（结论）」为准"
                : "Agent 结论未包含 recommended_action，无处置建议",
          }}
          dataSource={data.dispositions ?? []}
          columns={[
            { title: "建议", dataIndex: "suggested_action" },
            { title: "状态", dataIndex: "status", render: (v) => <Tag>{v}</Tag> },
            {
              title: "操作",
              render: (_, row) =>
                row.status === "suggested" ? (
                  <Button
                    size="small"
                    loading={confirmDisp.isPending && confirmDisp.variables === row.id}
                    onClick={() => confirmDisp.mutate(row.id)}
                  >
                    确认
                  </Button>
                ) : null,
            },
          ]}
        />
        {pendingDispositions.length > 0 && (
          <Typography.Text type="secondary" style={{ display: "block", marginTop: 8 }}>
            共 {pendingDispositions.length} 条待确认处置建议
          </Typography.Text>
        )}
      </Card>
    </Space>
  );
}
