import { Alert, Button, Card, Space, Typography, Upload, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
    grace_remaining_hours?: number;
  };
};

type FingerprintResponse = {
  fingerprint?: string;
  source?: string;
  hint?: string;
};

export default function LicensePage() {
  const { t } = useI18n();
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
      message.success(t("license.importOk"));
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
        message={pro ? t("license.proActive") : t("license.communityMode")}
        description={pro ? t("license.proUnlocked") : t("license.communityHint")}
      />

      <Card title={t("license.titleStatus")} loading={isLoading}>
        {isError ? (
          <Typography.Text type="danger">{formatApiError(error)}</Typography.Text>
        ) : (
          <>
            <Typography.Paragraph>
              {t("license.edition")}：
              <Typography.Text code>{data?.edition ?? "community"}</Typography.Text>
              {" · "}
              {t("license.status")}：
              <Typography.Text code>{lic?.status ?? "—"}</Typography.Text>
            </Typography.Paragraph>
            {lic?.client_name && (
              <Typography.Paragraph>
                {t("license.client")}：{lic.client_name}
              </Typography.Paragraph>
            )}
            {lic?.expiry_date && (
              <Typography.Paragraph>
                {t("license.expiry")}：{lic.expiry_date}
                {typeof lic.days_remaining === "number"
                  ? t("license.daysLeft", { days: lic.days_remaining })
                  : ""}
              </Typography.Paragraph>
            )}
            <Typography.Paragraph type="secondary">
              {lic?.status === "community"
                ? t("license.communityHint")
                : lic?.hint || t("license.bannerStatus", { status: lic?.status ?? "—" })}
            </Typography.Paragraph>
          </>
        )}
      </Card>

      <Card title={t("license.titleFingerprint")}>
        <Typography.Paragraph copyable={fp?.fingerprint ? { text: fp.fingerprint } : false}>
          {fp?.fingerprint ?? t("license.loading")}
        </Typography.Paragraph>
        <Typography.Text type="secondary">
          {t("license.importHint")}
        </Typography.Text>
      </Card>

      <Card title={t("license.titleImport")}>
        <Typography.Paragraph type="secondary">{t("license.importHint")}</Typography.Paragraph>
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
            {t("license.pickFile")}
          </Button>
        </Upload>
      </Card>
    </Space>
  );
}
