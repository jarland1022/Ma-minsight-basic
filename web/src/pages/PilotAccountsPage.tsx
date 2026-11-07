import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, formatApiError } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";

type UserRow = {
  id: string;
  username: string;
  role: string;
  is_active: boolean;
  is_readonly: boolean;
  expires_at: string | null;
  revoked_at: string | null;
  pilot_label: string | null;
  allowed_cidrs: string[];
  mfa_required?: boolean;
  mfa_enrolled?: boolean;
  last_login_at: string | null;
  last_login_ip: string | null;
  created_at: string | null;
};

type AuditRow = {
  id: string;
  created_at: string | null;
  actor_type: string | null;
  actor_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  detail: Record<string, unknown>;
};

type MfaReveal = {
  username: string;
  password?: string;
  expires_at?: string;
  mfa_secret?: string;
  otpauth_uri?: string;
  qr_png_data_url?: string;
};

export default function PilotAccountsPage() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [createdCreds, setCreatedCreds] = useState<MfaReveal | null>(null);

  const { data: me } = useQuery({
    queryKey: ["auth-me"],
    queryFn: async () => (await api.get("/auth/me")).data,
  });

  const { data, isLoading } = useQuery<{ items: UserRow[] }>({
    queryKey: ["users"],
    queryFn: async () => (await api.get("/users")).data,
    enabled: Boolean(me?.is_admin),
  });

  const { data: audits, isFetching: auditLoading, refetch: refetchAudits } = useQuery<{
    items: AuditRow[];
  }>({
    queryKey: ["audit-logs"],
    queryFn: async () => (await api.get("/audit-logs", { params: { limit: 100 } })).data,
    enabled: Boolean(me?.is_admin),
  });

  const createPilot = useMutation({
    mutationFn: async (values: {
      username: string;
      pilot_label?: string;
      business_days: number;
      allowed_cidrs?: string;
      mfa_required?: boolean;
    }) => {
      const cidrs = (values.allowed_cidrs || "")
        .split(/[\n,]/)
        .map((s) => s.trim())
        .filter(Boolean);
      return (
        await api.post("/users/pilots", {
          username: values.username,
          pilot_label: values.pilot_label || undefined,
          business_days: values.business_days,
          allowed_cidrs: cidrs,
          mfa_required: Boolean(values.mfa_required),
        })
      ).data;
    },
    onSuccess: (res) => {
      setCreatedCreds({
        username: res.user.username,
        password: res.temporary_password,
        expires_at: res.expires_at,
        mfa_secret: res.mfa_secret,
        otpauth_uri: res.otpauth_uri,
        qr_png_data_url: res.qr_png_data_url,
      });
      message.success(t("pilots.created"));
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (e) => message.error(formatApiError(e)),
  });

  const revoke = useMutation({
    mutationFn: (id: string) => api.post(`/users/${id}/revoke`),
    onSuccess: () => {
      message.success(t("pilots.revoked"));
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (e) => message.error(formatApiError(e)),
  });

  const resetMfa = useMutation({
    mutationFn: (id: string) => api.post(`/users/${id}/mfa/reset`),
    onSuccess: () => {
      message.success(t("pilots.mfaResetOk"));
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (e) => message.error(formatApiError(e)),
  });

  const reissueMfa = useMutation({
    mutationFn: async (id: string) => (await api.post(`/users/${id}/mfa/reissue`)).data,
    onSuccess: (res) => {
      setCreatedCreds({
        username: res.user.username,
        mfa_secret: res.mfa_secret,
        otpauth_uri: res.otpauth_uri,
        qr_png_data_url: res.qr_png_data_url,
      });
      message.success(t("pilots.mfaReissueOk"));
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (e) => message.error(formatApiError(e)),
  });

  const expireBatch = useMutation({
    mutationFn: () => api.post("/users/expire-pilots"),
    onSuccess: (res) => {
      message.success(t("pilots.expiredBatch", { n: res.data?.revoked_count ?? 0 }));
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (e) => message.error(formatApiError(e)),
  });

  if (me && !me.is_admin) {
    return <Alert type="warning" showIcon message={t("pilots.adminOnly")} />;
  }

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Card title={t("pilots.createTitle")}>
        <Typography.Paragraph type="secondary">{t("pilots.createHint")}</Typography.Paragraph>
        <Alert type="info" showIcon style={{ marginBottom: 12 }} message={t("pilots.mfaReserved")} />
        <Form
          layout="vertical"
          style={{ maxWidth: 520 }}
          initialValues={{ business_days: 5, mfa_required: true }}
          onFinish={(v) => createPilot.mutate(v)}
        >
          <Form.Item
            name="username"
            label={t("pilots.username")}
            rules={[{ required: true, min: 3 }]}
          >
            <Input placeholder="pilot-acme-01" />
          </Form.Item>
          <Form.Item name="pilot_label" label={t("pilots.label")}>
            <Input placeholder="Acme Corp 5-day pilot" />
          </Form.Item>
          <Form.Item
            name="business_days"
            label={t("pilots.businessDays")}
            rules={[{ required: true }]}
          >
            <InputNumber min={1} max={30} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="allowed_cidrs" label={t("pilots.cidrs")}>
            <Input.TextArea
              rows={2}
              placeholder={"203.0.113.0/24\n198.51.100.10/32"}
            />
          </Form.Item>
          <Form.Item name="mfa_required" label={t("pilots.mfaRequired")} valuePropName="checked">
            <Switch />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={createPilot.isPending}>
            {t("pilots.create")}
          </Button>
        </Form>

        {createdCreds && (
          <Alert
            style={{ marginTop: 16 }}
            type="success"
            showIcon
            message={createdCreds.password ? t("pilots.credOnce") : t("pilots.mfaQrOnce")}
            description={
              <Space direction="vertical" size="small">
                <div>
                  {t("pilots.username")}: <code>{createdCreds.username}</code>
                </div>
                {createdCreds.password && (
                  <div>
                    {t("pilots.password")}: <code>{createdCreds.password}</code>
                  </div>
                )}
                {createdCreds.expires_at && (
                  <div>
                    {t("pilots.expires")}: <code>{createdCreds.expires_at}</code>
                  </div>
                )}
                {createdCreds.qr_png_data_url && (
                  <div>
                    <img
                      src={createdCreds.qr_png_data_url}
                      alt="MFA QR"
                      width={160}
                      height={160}
                    />
                  </div>
                )}
                {createdCreds.mfa_secret && (
                  <Typography.Text copyable={{ text: createdCreds.mfa_secret }}>
                    {t("login.mfaSecret")}: <code>{createdCreds.mfa_secret}</code>
                  </Typography.Text>
                )}
              </Space>
            }
          />
        )}
      </Card>

      <Card
        title={t("pilots.listTitle")}
        extra={
          <Button onClick={() => expireBatch.mutate()} loading={expireBatch.isPending}>
            {t("pilots.expireNow")}
          </Button>
        }
      >
        <Table<UserRow>
          loading={isLoading}
          rowKey="id"
          dataSource={data?.items ?? []}
          pagination={{ pageSize: 20 }}
          columns={[
            { title: t("pilots.username"), dataIndex: "username" },
            {
              title: t("pilots.role"),
              dataIndex: "role",
              render: (v, row) => (
                <Space wrap>
                  <Tag color={v === "pilot_readonly" ? "blue" : v === "admin" ? "red" : "default"}>
                    {v}
                  </Tag>
                  {!row.is_active && <Tag>inactive</Tag>}
                  {row.mfa_required && row.mfa_enrolled && (
                    <Tag color="purple">{t("pilots.mfaEnrolled")}</Tag>
                  )}
                  {row.mfa_required && !row.mfa_enrolled && (
                    <Tag color="orange">{t("pilots.mfaPending")}</Tag>
                  )}
                </Space>
              ),
            },
            { title: t("pilots.label"), dataIndex: "pilot_label" },
            {
              title: t("pilots.expires"),
              dataIndex: "expires_at",
              render: (v) => (v ? String(v).replace("T", " ").slice(0, 19) : "—"),
            },
            {
              title: t("pilots.cidrs"),
              dataIndex: "allowed_cidrs",
              render: (v: string[]) => (v?.length ? v.join(", ") : "—"),
            },
            {
              title: t("pilots.lastLogin"),
              render: (_, row) =>
                row.last_login_at
                  ? `${String(row.last_login_at).slice(0, 19)} @ ${row.last_login_ip || "?"}`
                  : "—",
            },
            {
              title: t("pilots.actions"),
              render: (_, row) =>
                row.is_active ? (
                  <Space wrap size="small">
                    <Button
                      danger
                      size="small"
                      onClick={() => revoke.mutate(row.id)}
                      loading={revoke.isPending}
                    >
                      {t("pilots.revoke")}
                    </Button>
                    {row.mfa_required && (
                      <>
                        <Popconfirm
                          title={t("pilots.resetMfa")}
                          onConfirm={() => resetMfa.mutate(row.id)}
                        >
                          <Button size="small" loading={resetMfa.isPending}>
                            {t("pilots.resetMfa")}
                          </Button>
                        </Popconfirm>
                        <Button
                          size="small"
                          onClick={() => reissueMfa.mutate(row.id)}
                          loading={reissueMfa.isPending}
                        >
                          {t("pilots.reissueMfa")}
                        </Button>
                      </>
                    )}
                  </Space>
                ) : (
                  "—"
                ),
            },
          ]}
        />
      </Card>

      <Card
        title={t("pilots.auditTitle")}
        extra={
          <Button onClick={() => refetchAudits()} loading={auditLoading}>
            {t("pilots.refreshAudit")}
          </Button>
        }
      >
        <Table<AuditRow>
          size="small"
          loading={auditLoading}
          rowKey="id"
          dataSource={audits?.items ?? []}
          pagination={{ pageSize: 15 }}
          columns={[
            {
              title: t("pilots.auditTime"),
              dataIndex: "created_at",
              render: (v) => (v ? String(v).replace("T", " ").slice(0, 19) : "—"),
            },
            { title: t("pilots.auditAction"), dataIndex: "action" },
            { title: t("pilots.auditActor"), dataIndex: "actor_id" },
            {
              title: t("pilots.auditResource"),
              render: (_, row) =>
                row.resource_type
                  ? `${row.resource_type}:${row.resource_id || ""}`
                  : "—",
            },
            {
              title: t("pilots.auditDetail"),
              dataIndex: "detail",
              ellipsis: true,
              render: (v) => (v ? JSON.stringify(v) : "—"),
            },
          ]}
        />
      </Card>
    </Space>
  );
}
