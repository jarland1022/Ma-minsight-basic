import { Card, Space, Table, Typography, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import IngestionDiagnosticsPanel from "../components/IngestionDiagnosticsPanel";
import ManualRunPanel from "../components/ManualRunPanel";
import type { ConfigRow } from "../types/api";

export default function SettingsPage() {
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
      message.success("配置已更新");
      qc.invalidateQueries({ queryKey: ["config"] });
    },
  });

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Card title="告警入库故障排查">
        <IngestionDiagnosticsPanel />
      </Card>

      <Card title="手动运行流水线（管理员）">
        <ManualRunPanel />
      </Card>

      <Card title="调查 SOP 模板（只读）">
        <Typography.Paragraph type="secondary">
          结构化假设模板与推荐 Skill，供运维核对 Agent 调查策略。
        </Typography.Paragraph>
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
                推荐 Skill：{(sop.recommended_skills ?? []).join(", ") || "—"}
              </Typography.Text>
              {sop.hypothesis_template ? (
                <pre style={{ whiteSpace: "pre-wrap", marginTop: 8, fontSize: 12 }}>
                  {JSON.stringify(sop.hypothesis_template, null, 2)}
                </pre>
              ) : (
                <Typography.Text type="secondary">无 hypothesis_template</Typography.Text>
              )}
            </Card>
          ),
        )}
      </Card>

      <Card title="系统配置">
        <Table<ConfigRow>
          loading={isLoading}
          rowKey="key"
          dataSource={configs ?? []}
          pagination={{ pageSize: 20 }}
          columns={[
            { title: "配置项", dataIndex: "key", width: 280 },
            {
              title: "值",
              dataIndex: "value",
              render: (v) => <Typography.Text code>{JSON.stringify(v)}</Typography.Text>,
            },
            { title: "说明", dataIndex: "description", ellipsis: true },
          ]}
          expandable={{
            expandedRowRender: (row) => (
              <Typography.Paragraph editable={{ onChange: (text) => {
                try {
                  updateConfig.mutate({ key: row.key, value: JSON.parse(text) });
                } catch {
                  message.error("JSON 格式无效");
                }
              } }}>
                {JSON.stringify(row.value, null, 2)}
              </Typography.Paragraph>
            ),
          }}
        />
      </Card>
    </Space>
  );
}
