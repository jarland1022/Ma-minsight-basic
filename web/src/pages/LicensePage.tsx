import { Alert, Card, Space, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { api, formatApiError } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";

type LicenseStatusResponse = {
  edition?: string;
  pro_enabled?: boolean;
  license?: {
    status?: string;
    hint?: string;
    client_name?: string;
    expiry_date?: string;
    days_remaining?: number;
  };
};

export default function LicensePage() {
  const { t, lang } = useI18n();
  const { data, isLoading, isError, error } = useQuery<LicenseStatusResponse>({
    queryKey: ["license-status"],
    queryFn: async () => (await api.get("/license/status")).data,
  });

  const lic = data?.license;
  const pro = Boolean(data?.pro_enabled);

  const title =
    lang === "zh" ? "本部署为专业版（AI-SEC）" : "This deployment is Professional (AI-SEC)";
  const body =
    lang === "zh"
      ? "当前仓库/镜像按专业版能力运行（AI Agent、人工协查、防御资产、评测等默认可用），无需再导入社区版 license.lic。"
      : "This repo/image runs with Professional capabilities (AI Agent, human review, defense assets, eval) enabled by default. Community license.lic import is not used here.";

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Alert type={pro ? "success" : "info"} showIcon message={title} description={body} />

      <Card title={t("license.titleStatus")} loading={isLoading}>
        {isError ? (
          <Typography.Text type="danger">{formatApiError(error)}</Typography.Text>
        ) : (
          <>
            <Typography.Paragraph>
              {t("license.edition")}：
              <Typography.Text code>{data?.edition ?? "professional"}</Typography.Text>
              {" · "}
              {t("license.status")}：
              <Typography.Text code>{lic?.status ?? "active"}</Typography.Text>
            </Typography.Paragraph>
            {lic?.client_name && (
              <Typography.Paragraph>
                {t("license.client")}：{lic.client_name}
              </Typography.Paragraph>
            )}
            <Typography.Paragraph type="secondary">
              {lic?.hint || t("license.proUnlocked")}
            </Typography.Paragraph>
          </>
        )}
      </Card>
    </Space>
  );
}
