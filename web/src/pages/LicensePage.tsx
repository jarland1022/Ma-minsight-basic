import { Alert, Button, Card, Space, Typography, Upload, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "../api/client";

type LicenseStatusResponse = {
  edition?: string;
  pro_enabled?: boolean;
  license?: {
    status?: string;
    hint?: string;
    client_name?: string;
    expiry_date?: string;
    days_remaining?: number;
    grace_remaining_hours?: number;
  };
};

type FingerprintResponse = {
  fingerprint?: string;
  source?: string;
  hint?: string;
};

export default function LicensePage() {
  const qc = useQueryClient();
  const { data, isLoading, isError, error } = useQuery<LicenseStatusResponse>({
    queryKey: ["license-status"],
    queryFn: async () => (await api.get("/license/status")).data,
  });
  const { data: fp } = useQuery<FingerprintResponse>({
    queryKey: ["license-fingerprint"],
    queryFn: async () => (await api.get("/license/fingerprint")).data,
  });

  const importLic = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return (await api.post("/license/import", form)).data;
    },
    onSuccess: () => {
      message.success("License 已导入；请重启应用以加载专业版调度器");
      qc.invalidateQueries({ queryKey: ["license-status"] });
    },
    onError: (err) => message.error(formatApiError(err)),
  });

  const lic = data?.license;
  const pro = Boolean(data?.pro_enabled);

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Alert
        type={pro ? "success" : "info"}
        showIcon
        message={pro ? "专业版已激活" : "当前为社区版能力"}
        description={
          pro
            ? "AI Agent、企微协查、防御资产与评测已解锁。"
            : "社区版可免费使用：告警入库 → 初筛 → 聚合 → 事件台与技能库。导入专业版 License 后解锁 AI 深度研判等能力。"
        }
      />

      <Card title="License 状态" loading={isLoading}>
        {isError ? (
          <Typography.Text type="danger">{formatApiError(error)}</Typography.Text>
        ) : (
          <>
            <Typography.Paragraph>
              发行版：<Typography.Text code>{data?.edition ?? "community"}</Typography.Text>
              {" · "}
              状态：<Typography.Text code>{lic?.status ?? "—"}</Typography.Text>
            </Typography.Paragraph>
            {lic?.client_name && (
              <Typography.Paragraph>客户：{lic.client_name}</Typography.Paragraph>
            )}
            {lic?.expiry_date && (
              <Typography.Paragraph>
                到期：{lic.expiry_date}
                {typeof lic.days_remaining === "number" ? `（剩余 ${lic.days_remaining} 天）` : ""}
              </Typography.Paragraph>
            )}
            {lic?.hint && <Typography.Paragraph type="secondary">{lic.hint}</Typography.Paragraph>}
          </>
        )}
      </Card>

      <Card title="机器指纹（购买专业版时发给厂商）">
        <Typography.Paragraph copyable={fp?.fingerprint ? { text: fp.fingerprint } : false}>
          {fp?.fingerprint ?? "加载中…"}
        </Typography.Paragraph>
        <Typography.Text type="secondary">{fp?.hint}</Typography.Text>
      </Card>

      <Card title="导入专业版 License">
        <Typography.Paragraph type="secondary">
          联系微信 <Typography.Text code>jarlandliu</Typography.Text> 或邮箱{" "}
          <Typography.Text code>jarland@mingansec.com</Typography.Text> 获取{" "}
          <Typography.Text code>license.lic</Typography.Text>
          （需同时部署厂商提供的公钥）。导入后请重启服务。
        </Typography.Paragraph>
        <Upload
          accept=".lic"
          maxCount={1}
          showUploadList={false}
          beforeUpload={(file) => {
            importLic.mutate(file);
            return false;
          }}
        >
          <Button type="primary" loading={importLic.isPending}>
            选择 .lic 文件
          </Button>
        </Upload>
      </Card>
    </Space>
  );
}
