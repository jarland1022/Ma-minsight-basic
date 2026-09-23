import { Alert, Button, Card, List, Space, Table, Tag, Typography, message } from "antd";
import { isAxiosError } from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import UserGuidePanel from "../components/UserGuidePanel";
import { PAGE_GUIDES } from "../content/userGuide";
import type { PendingDispositionRow, PendingSimulationRow } from "../types/api";

export default function DefenseAssetsPage() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["pending"],
    queryFn: async () => (await api.get("/console/pending")).data,
  });

  const confirmWl = useMutation({
    mutationFn: (id: string) => api.post(`/whitelist-candidates/${id}/confirm`),
    onSuccess: () => {
      message.success("已确认");
      qc.invalidateQueries({ queryKey: ["pending"] });
    },
  });

  const applyProfile = useMutation({
    mutationFn: (id: string) => api.post(`/profile-suggestions/${id}/apply`),
    onSuccess: () => {
      message.success("已应用到画像记忆（非白名单）");
      qc.invalidateQueries({ queryKey: ["pending"] });
    },
  });

  const confirmDisp = useMutation({
    mutationFn: (id: string) => api.post(`/disposition/${id}/confirm`, { confirmed_action: null }),
    onSuccess: () => {
      message.success("处置已确认");
      qc.invalidateQueries({ queryKey: ["pending"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["noisy-rules"] });
    },
    onError: (error) => {
      const detail = isAxiosError(error) ? error.response?.data?.detail : undefined;
      message.error(typeof detail === "string" ? detail : "处置确认失败");
    },
  });

  const rejectDisp = useMutation({
    mutationFn: (id: string) => api.post(`/disposition/${id}/reject`),
    onSuccess: () => {
      message.success("已拒绝");
      qc.invalidateQueries({ queryKey: ["pending"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["noisy-rules"] });
    },
    onError: (error) => {
      const detail = isAxiosError(error) ? error.response?.data?.detail : undefined;
      message.error(typeof detail === "string" ? detail : "拒绝失败");
    },
  });

  const approveSim = useMutation({
    mutationFn: (id: string) => api.post(`/disposition-simulations/${id}/approve`),
    onSuccess: () => {
      message.success("推演已批准（仅审计记录，不会自动执行）");
      qc.invalidateQueries({ queryKey: ["pending"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["noisy-rules"] });
    },
    onError: (error) => {
      const detail = isAxiosError(error) ? error.response?.data?.detail : undefined;
      message.error(typeof detail === "string" ? detail : "批准失败");
    },
  });

  const rejectSim = useMutation({
    mutationFn: (id: string) => api.post(`/disposition-simulations/${id}/reject`),
    onSuccess: () => {
      message.success("推演已拒绝");
      qc.invalidateQueries({ queryKey: ["pending"] });
    },
    onError: (error) => {
      const detail = isAxiosError(error) ? error.response?.data?.detail : undefined;
      message.error(typeof detail === "string" ? detail : "拒绝失败");
    },
  });

  const dispositions: PendingDispositionRow[] = data?.dispositions ?? [];
  const simulations: PendingSimulationRow[] = data?.disposition_simulations ?? [];

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <UserGuidePanel guide={PAGE_GUIDES.defenseAssets} defaultExpanded />
      <Alert
        type="warning"
        showIcon
        message="本页所有「确认 / 批准」按钮都不会自动执行封禁或隔离"
        description="它们仅用于记录您已审阅 AI 建议。真实处置请在防火墙、WAF、主机安全等产品中由运维操作。"
      />
      <Card title="白名单候选（≥3 次确认升格 active 规则）">
        <Typography.Paragraph type="secondary">
          当 AI 多次判断某类告警为误报时，会建议加入白名单。您每点一次「确认」计一次；满 3 次后系统自动生成白名单规则，减少同类告警打扰。
        </Typography.Paragraph>
        <List
          dataSource={data?.whitelist_candidates ?? []}
          renderItem={(item: { id: string; human_confirmations: number; reason: string }) => (
            <List.Item
              actions={[
                <Button key="c" onClick={() => confirmWl.mutate(item.id)}>
                  确认 ({item.human_confirmations}/3)
                </Button>,
              ]}
            >
              {item.reason || item.id}
            </List.Item>
          )}
        />
      </Card>

      <Card title="画像更新建议 → entity_profile_memories">
        <Typography.Paragraph type="secondary">批准仅写入画像参考，不能自动归档。</Typography.Paragraph>
        <List
          dataSource={data?.profile_suggestions ?? []}
          renderItem={(item: { id: string; suggested_changes: { content?: string } }) => (
            <List.Item
              actions={[
                <Button key="a" onClick={() => applyProfile.mutate(item.id)}>
                  批准
                </Button>,
              ]}
            >
              {item.suggested_changes?.content || item.id}
            </List.Item>
          )}
        />
      </Card>

      <Card
        title={`待确认处置${dispositions.length ? `（${dispositions.length}）` : ""}`}
        extra={
          <Typography.Text type="secondary">
            建议来自 Agent 调查结论，确认后仅作审计记录，不会自动执行
          </Typography.Text>
        }
      >
        <Table<PendingDispositionRow>
          rowKey="id"
          pagination={{ pageSize: 10, showSizeChanger: true }}
          dataSource={dispositions}
          locale={{ emptyText: "暂无待确认处置" }}
          columns={[
            {
              title: "事件",
              key: "event",
              width: 280,
              render: (_, row) =>
                row.event_id ? (
                  <Space direction="vertical" size={0}>
                    <Link to={`/events/${row.event_id}`}>{row.event_title || row.event_id}</Link>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {row.event_status && <Tag>{row.event_status}</Tag>}
                      {row.primary_category}
                    </Typography.Text>
                  </Space>
                ) : (
                  "—"
                ),
            },
            {
              title: "主机 / 用户",
              key: "asset",
              width: 160,
              render: (_, row) => (
                <Typography.Text>
                  {row.aggregate_host_name || "—"}
                  {row.aggregate_user_name ? ` / ${row.aggregate_user_name}` : ""}
                </Typography.Text>
              ),
            },
            {
              title: "风险",
              dataIndex: "risk_score",
              width: 72,
              render: (v) => (v != null ? Number(v).toFixed(0) : "—"),
            },
            {
              title: "裁决",
              dataIndex: "verdict",
              width: 140,
              render: (v) => (v ? <Tag color="blue">{v}</Tag> : "—"),
            },
            {
              title: "处置建议",
              dataIndex: "suggested_action",
              ellipsis: true,
            },
            {
              title: "产生时间",
              dataIndex: "created_at",
              width: 168,
              render: (v) => (v ? String(v).slice(0, 19).replace("T", " ") : "—"),
            },
            {
              title: "操作",
              key: "actions",
              width: 140,
              fixed: "right",
              render: (_, row) => (
                <Space>
                  <Button
                    type="primary"
                    size="small"
                    loading={confirmDisp.isPending && confirmDisp.variables === row.id}
                    onClick={() => confirmDisp.mutate(row.id)}
                  >
                    确认
                  </Button>
                  <Button
                    size="small"
                    loading={rejectDisp.isPending && rejectDisp.variables === row.id}
                    onClick={() => rejectDisp.mutate(row.id)}
                  >
                    拒绝
                  </Button>
                </Space>
              ),
            },
          ]}
          scroll={{ x: 1100 }}
        />
      </Card>

      <Card
        title={`处置推演审批${simulations.length ? `（${simulations.length}）` : ""}`}
        extra={
          <Typography.Text type="secondary">
            Agent 调用 simulate_disposition 的只读模拟结果；批准后不触发真实封禁/隔离
          </Typography.Text>
        }
      >
        <Table<PendingSimulationRow>
          rowKey="id"
          pagination={{ pageSize: 10, showSizeChanger: true }}
          dataSource={simulations}
          locale={{ emptyText: "暂无待审批推演" }}
          columns={[
            {
              title: "事件",
              key: "event",
              width: 240,
              render: (_, row) =>
                row.event_id ? (
                  <Link to={`/events/${row.event_id}`}>{row.event_title || row.event_id}</Link>
                ) : (
                  "—"
                ),
            },
            {
              title: "动作",
              dataIndex: "action_type",
              width: 120,
              render: (v) => <Tag>{v}</Tag>,
            },
            {
              title: "目标",
              key: "target",
              width: 160,
              render: (_, row) => {
                const p = row.action_params ?? {};
                return String(p.ip || p.host_name || p.user_name || "—");
              },
            },
            {
              title: "影响主机",
              dataIndex: "affected_host_count",
              width: 88,
              render: (v) => v ?? "—",
            },
            {
              title: "预估中断(分)",
              dataIndex: "estimated_downtime_minutes",
              width: 110,
              render: (v) => v ?? "—",
            },
            {
              title: "业务系统",
              key: "biz",
              ellipsis: true,
              render: (_, row) => (row.business_systems?.length ? row.business_systems.join(", ") : "—"),
            },
            {
              title: "操作",
              key: "actions",
              width: 140,
              fixed: "right",
              render: (_, row) => (
                <Space>
                  <Button
                    type="primary"
                    size="small"
                    loading={approveSim.isPending && approveSim.variables === row.id}
                    onClick={() => approveSim.mutate(row.id)}
                  >
                    批准
                  </Button>
                  <Button
                    size="small"
                    loading={rejectSim.isPending && rejectSim.variables === row.id}
                    onClick={() => rejectSim.mutate(row.id)}
                  >
                    拒绝
                  </Button>
                </Space>
              ),
            },
          ]}
          scroll={{ x: 1000 }}
        />
      </Card>
    </Space>
  );
}
