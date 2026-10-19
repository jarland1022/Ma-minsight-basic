import { Card, Space, Table, Typography, message } from "antd";
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
