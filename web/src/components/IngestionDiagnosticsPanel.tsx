import type { ReactNode } from "react";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  MinusCircleOutlined,
  ReloadOutlined,
  ToolOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Collapse,
  Descriptions,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "../api/client";
import type { DiagnosticCheck, IngestionDiagnosticsReport } from "../types/api";

const STATUS_ICON: Record<string, ReactNode> = {
  ok: <CheckCircleOutlined style={{ color: "#52c41a" }} />,
  warn: <ExclamationCircleOutlined style={{ color: "#faad14" }} />,
  error: <CloseCircleOutlined style={{ color: "#ff4d4f" }} />,
  info: <InfoCircleOutlined style={{ color: "#1677ff" }} />,
  skip: <MinusCircleOutlined style={{ color: "#999" }} />,
};

const OVERALL_ALERT: Record<string, "success" | "warning" | "error" | "info"> = {
  ok: "success",
  warn: "warning",
  error: "error",
};

function formatTs(iso: string | null | undefined): string {
  if (!iso) return "—";
  return iso.slice(0, 19).replace("T", " ");
}

function CheckItem({ check }: { check: DiagnosticCheck }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <Space align="start">
        {STATUS_ICON[check.status] ?? STATUS_ICON.info}
        <div>
          <Typography.Text strong>{check.label}</Typography.Text>
          <div>
            <Typography.Text>{check.message}</Typography.Text>
          </div>
          {check.detail && (
            <Typography.Paragraph type="secondary" style={{ marginBottom: 4, fontSize: 12 }}>
              {check.detail}
            </Typography.Paragraph>
          )}
          {check.suggestion && (
            <Typography.Text type="warning" style={{ fontSize: 12 }}>
              建议：{check.suggestion}
            </Typography.Text>
          )}
        </div>
      </Space>
    </div>
  );
}

export default function IngestionDiagnosticsPanel() {
  const qc = useQueryClient();
  const { data: me } = useQuery({
    queryKey: ["auth-me"],
    queryFn: async () => (await api.get("/auth/me")).data,
  });
  const isAdmin = me?.is_admin === true;

  const {
    data: report,
    isLoading,
    isFetching,
    refetch,
  } = useQuery<IngestionDiagnosticsReport>({
    queryKey: ["diagnostics-ingestion"],
    queryFn: async () => (await api.get("/diagnostics/ingestion")).data,
    staleTime: 30_000,
  });

  const extendLookback = useMutation({
    mutationFn: async (sourceId: string) =>
      (
        await api.post(`/diagnostics/ingestion/sources/${sourceId}/extend-lookback`, {
          lookback_hours: 168,
          reset_cursor: true,
        })
      ).data,
    onSuccess: () => {
      message.success("已扩大回溯至 7 天并重置游标，请点击「告警入库」重新拉取");
      qc.invalidateQueries({ queryKey: ["diagnostics-ingestion"] });
    },
    onError: (error) => message.error(formatApiError(error)),
  });

  const realSources = report?.sources.filter((s) => s.adapter_type !== "health_probe") ?? [];

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="middle">
      <Alert
        type="info"
        showIcon
        message="一键排查告警入库"
        description="自动检测 Wazuh Indexer 连接、游标状态与回溯窗口，并给出可操作的修复建议。无需登录服务器或执行 SQL。"
      />

      <Space wrap>
        <Button
          type="primary"
          icon={<ReloadOutlined />}
          loading={isLoading || isFetching}
          onClick={() => refetch()}
        >
          重新检测
        </Button>
      </Space>

      {isLoading && !report ? (
        <Spin tip="正在检测…" />
      ) : report ? (
        <>
          <Alert
            type={OVERALL_ALERT[report.overall_status] ?? "info"}
            showIcon
            message={`整体状态：${report.overall_status === "ok" ? "正常" : report.overall_status === "warn" ? "需关注" : "异常"}`}
            description={report.summary}
          />

          <Alert
            type={report.geolite2_ready ? "success" : "info"}
            showIcon
            message={
              report.geolite2_ready
                ? "GeoIP 归属地解析已启用"
                : "GeoIP 归属地解析未启用"
            }
            description={
              report.geolite2_ready
                ? `数据库：${report.geolite2_path}`
                : "将 GeoLite2-City.mmdb 放到 ./data/geoip/ 并设置 GEOLITE2_CITY_PATH 后，新入库告警会自动解析源 IP 国家/城市。"
            }
          />

          <Collapse
            defaultActiveKey={realSources.map((s) => s.data_source_id)}
            items={report.sources.map((source) => ({
              key: source.data_source_id,
              label: (
                <Space>
                  <ToolOutlined />
                  <span>{source.name}</span>
                  <Tag>{source.adapter_type}</Tag>
                  {!source.is_active && <Tag color="default">已禁用</Tag>}
                  <Tag
                    color={
                      source.overall_status === "ok"
                        ? "success"
                        : source.overall_status === "warn"
                          ? "warning"
                          : "error"
                    }
                  >
                    {source.overall_status === "ok"
                      ? "正常"
                      : source.overall_status === "warn"
                        ? "需关注"
                        : "异常"}
                  </Tag>
                </Space>
              ),
              children: (
                <Space direction="vertical" style={{ width: "100%" }} size="middle">
                  {source.checks.map((check) => (
                    <CheckItem key={check.id} check={check} />
                  ))}

                  <Descriptions size="small" bordered column={2}>
                    <Descriptions.Item label="库内告警数">
                      {source.stats.alerts_in_db}
                    </Descriptions.Item>
                    <Descriptions.Item label="游标位置">
                      {formatTs(source.stats.cursor_last_occurred_at) || "空（初始回溯）"}
                    </Descriptions.Item>
                    <Descriptions.Item label="Indexer 最新告警">
                      {formatTs(source.stats.indexer_latest_at)}
                    </Descriptions.Item>
                    <Descriptions.Item label="Indexer 总量">
                      {source.stats.indexer_total_alerts ?? "—"}
                    </Descriptions.Item>
                    <Descriptions.Item label="回溯窗口">
                      {source.stats.initial_lookback_hours != null
                        ? `${source.stats.initial_lookback_hours} 小时`
                        : "—"}
                    </Descriptions.Item>
                    <Descriptions.Item label="窗口内可拉取">
                      {source.stats.window_match_count ?? "—"}
                    </Descriptions.Item>
                    <Descriptions.Item label="Indexer 地址" span={2}>
                      {source.stats.indexer_url ?? "—"}
                    </Descriptions.Item>
                    <Descriptions.Item label="上次成功拉取">
                      {formatTs(source.stats.last_successful_run_at)}
                    </Descriptions.Item>
                    <Descriptions.Item label="检测时间">
                      {formatTs(report.generated_at)}
                    </Descriptions.Item>
                  </Descriptions>

                  {isAdmin &&
                    source.actions_available.includes("extend_lookback") && (
                      <Button
                        type="primary"
                        ghost
                        loading={extendLookback.isPending}
                        onClick={() => extendLookback.mutate(source.data_source_id)}
                      >
                        扩大回溯至 7 天并重置游标
                      </Button>
                    )}
                </Space>
              ),
            }))}
          />
        </>
      ) : null}
    </Space>
  );
}
