import {
  CloudDownloadOutlined,
  ExperimentOutlined,
  FilterOutlined,
  HeartOutlined,
  MergeCellsOutlined,
  MessageOutlined,
  PlayCircleOutlined,
  RobotOutlined,
  SafetyOutlined,
} from "@ant-design/icons";
import { Alert, Button, Card, Col, Row, Space, Steps, Tag, Typography, message } from "antd";
import type { ReactNode } from "react";
import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, formatApiError } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";

type PipelineGroup = "main" | "eval";
type Translate = (path: string, vars?: Record<string, string | number>) => string;

export type ManualPipelineDef = {
  key: string;
  label: string;
  summary: string;
  detail: string;
  effect: string;
  where: string;
  link?: string;
  group: PipelineGroup;
  icon: ReactNode;
  color: string;
};

const PIPELINE_META: {
  key: string;
  group: PipelineGroup;
  icon: ReactNode;
  color: string;
  link?: string;
}[] = [
  {
    key: "ingestion",
    group: "main",
    icon: <CloudDownloadOutlined />,
    color: "#1677ff",
    link: "/",
  },
  {
    key: "triage",
    group: "main",
    icon: <FilterOutlined />,
    color: "#13c2c2",
    link: "/",
  },
  {
    key: "aggregation",
    group: "main",
    icon: <MergeCellsOutlined />,
    color: "#722ed1",
    link: "/events",
  },
  {
    key: "investigation",
    group: "main",
    icon: <RobotOutlined />,
    color: "#eb2f96",
    link: "/license",
  },
  {
    key: "human_review",
    group: "main",
    icon: <MessageOutlined />,
    color: "#fa8c16",
    link: "/license",
  },
  {
    key: "defense_assets",
    group: "main",
    icon: <SafetyOutlined />,
    color: "#52c41a",
    link: "/license",
  },
  {
    key: "regression",
    group: "eval",
    icon: <ExperimentOutlined />,
    color: "#597ef7",
    link: "/license",
  },
  {
    key: "health_check",
    group: "eval",
    icon: <HeartOutlined />,
    color: "#f5222d",
    link: "/license",
  },
];

export function buildPipelines(t: Translate): ManualPipelineDef[] {
  return PIPELINE_META.map((meta) => ({
    ...meta,
    label: t(`pipelines.${meta.key}`),
    summary: t(`manual.${meta.key}Summary`),
    detail: t(`manual.${meta.key}Detail`),
    effect: t(`manual.${meta.key}Effect`),
    where: t(`manual.${meta.key}Where`),
  }));
}

const MAIN_FLOW_KEYS = PIPELINE_META.filter((p) => p.group === "main").map((p) => p.key);

function formatRunResult(
  t: Translate,
  key: string,
  result: Record<string, unknown> | undefined,
): string {
  if (!result) return t("manual.submitted");
  const errors = result.errors;
  if (Array.isArray(errors) && errors.length > 0) {
    return errors.map(String).join("；");
  }
  if (result.skipped_lock) return t("manual.lockBusy");
  if (result.skipped_budget) return t("manual.budgetDone");
  if (result.skipped_not_configured) return t("manual.notConfigured");
  if (result.skipped_disabled) return t("manual.disabled");

  switch (key) {
    case "ingestion": {
      const inserted = Number(result.inserted ?? 0);
      const dup = Number(result.duplicates ?? 0);
      const fetched = Number(result.fetched ?? 0);
      if (fetched === 0 && inserted === 0) {
        return t("manual.ingestZero");
      }
      return t("manual.ingestResult", { fetched, inserted, dup });
    }
    case "triage":
      return t("manual.processed", { n: Number(result.processed ?? 0) });
    case "aggregation":
      return t("manual.aggResult", {
        n: Number(result.processed ?? 0),
        created: Number(result.events_created ?? 0),
        merged: Number(result.events_merged ?? 0),
      });
    case "investigation":
      return t("manual.invResult", { n: Number(result.processed ?? 0) });
    case "human_review":
      return t("manual.hrResult", {
        d: Number(result.dispatched ?? 0),
        e: Number(result.expired ?? 0),
      });
    case "defense_assets":
      return t("manual.defResult", { n: Number(result.processed ?? 0) });
    case "regression":
    case "health_check":
      return t("manual.passResult", {
        passed: Number(result.passed ?? 0),
        total: Number(result.total ?? 0),
      });
    default:
      return t("manual.done");
  }
}

function formatLastRun(t: Translate, iso: string | null | undefined): string {
  if (!iso) return t("manual.never");
  return iso.slice(0, 19).replace("T", " ");
}

function PipelineCard({
  pipeline,
  lastRun,
  loading,
  disabled,
  onRun,
  t,
}: {
  pipeline: ManualPipelineDef;
  lastRun?: string | null;
  loading: boolean;
  disabled?: boolean;
  onRun: () => void;
  t: Translate;
}) {
  return (
    <Card
      size="small"
      hoverable
      styles={{ body: { height: "100%", display: "flex", flexDirection: "column" } }}
    >
      <Space align="start" style={{ marginBottom: 8 }}>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: 36,
            height: 36,
            borderRadius: 8,
            background: `${pipeline.color}18`,
            color: pipeline.color,
            fontSize: 18,
          }}
        >
          {pipeline.icon}
        </span>
        <div style={{ flex: 1 }}>
          <Typography.Text strong>{pipeline.label}</Typography.Text>
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {pipeline.summary}
            </Typography.Text>
          </div>
        </div>
      </Space>

      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 8, flex: 1 }}>
        {pipeline.detail}
      </Typography.Paragraph>

      <Space direction="vertical" size={4} style={{ width: "100%", marginBottom: 12 }}>
        <Typography.Text style={{ fontSize: 12 }}>
          <Tag color="blue" bordered={false}>
            {t("manual.expected")}
          </Tag>
          {pipeline.effect}
        </Typography.Text>
        <Typography.Text style={{ fontSize: 12 }}>
          <Tag color="green" bordered={false}>
            {t("manual.where")}
          </Tag>
          {pipeline.link ? <Link to={pipeline.link}>{pipeline.where}</Link> : pipeline.where}
        </Typography.Text>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {t("manual.lastRun", { time: formatLastRun(t, lastRun) })}
        </Typography.Text>
      </Space>

      <Button
        type="primary"
        ghost
        block
        icon={<PlayCircleOutlined />}
        loading={loading}
        disabled={disabled}
        onClick={onRun}
      >
        {t("manual.runNow")}
      </Button>
    </Card>
  );
}

export default function ManualRunPanel() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const pipelines = useMemo(() => buildPipelines(t), [t]);

  const { data: me } = useQuery({
    queryKey: ["auth-me"],
    queryFn: async () => (await api.get("/auth/me")).data,
  });
  const isAdmin = me?.is_admin === true;

  const { data: dashboard } = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get("/dashboard/summary")).data,
  });

  const pipelineLastRun: Record<string, string | null> = dashboard?.pipeline_last_run ?? {};

  const runPipeline = useMutation({
    mutationFn: async (key: string) => {
      const res = await api.post<{ pipeline: string; result: Record<string, unknown> }>(
        `/console/run/${key}`,
        {},
        { params: { limit: 10 } },
      );
      return { key, ...res.data };
    },
    onSuccess: ({ key, result }) => {
      const def = pipelines.find((p) => p.key === key);
      const summary = formatRunResult(t, key, result);
      const hasErrors = Array.isArray(result?.errors) && result.errors.length > 0;
      if (hasErrors) {
        message.error(`${def?.label ?? key}：${summary}`);
      } else {
        message.success(`${def?.label ?? key}：${summary}`);
      }
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["pending"] });
      qc.invalidateQueries({ queryKey: ["events"] });
      if (key === "ingestion") {
        qc.invalidateQueries({ queryKey: ["diagnostics-ingestion"] });
      }
    },
    onError: (error) => message.error(formatApiError(error)),
  });

  const mainPipelines = pipelines.filter((p) => p.group === "main");
  const evalPipelines = pipelines.filter((p) => p.group === "eval");

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="middle">
      {!isAdmin && me && (
        <Alert
          type="warning"
          showIcon
          message={t("manual.needAdmin")}
          description={t("manual.needAdminBody")}
        />
      )}

      <Alert
        type="info"
        showIcon
        message={t("manual.helpTitle")}
        description={t("manual.helpBody")}
      />

      <Card title={t("manual.mainFlow")} size="small">
        <Steps
          size="small"
          direction="horizontal"
          responsive={false}
          items={mainPipelines.map((p) => ({
            title: p.label,
            description: p.summary,
            icon: p.icon,
          }))}
          style={{ overflowX: "auto", paddingBottom: 8 }}
        />
        <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0, fontSize: 12 }}>
          {MAIN_FLOW_KEYS.map((k) => pipelines.find((p) => p.key === k)?.label).join(" → ")}
        </Typography.Paragraph>
      </Card>

      <div>
        <Typography.Title level={5} style={{ marginBottom: 12 }}>
          {t("manual.mainFlow")}
        </Typography.Title>
        <Row gutter={[16, 16]}>
          {mainPipelines.map((p) => (
            <Col xs={24} sm={12} lg={8} key={p.key}>
              <PipelineCard
                pipeline={p}
                lastRun={pipelineLastRun[p.key]}
                loading={runPipeline.isPending && runPipeline.variables === p.key}
                disabled={!isAdmin}
                onRun={() => runPipeline.mutate(p.key)}
                t={t}
              />
            </Col>
          ))}
        </Row>
      </div>

      <div>
        <Typography.Title level={5} style={{ marginBottom: 12 }}>
          {t("manual.evalFlow")}
        </Typography.Title>
        <Row gutter={[16, 16]}>
          {evalPipelines.map((p) => (
            <Col xs={24} sm={12} key={p.key}>
              <PipelineCard
                pipeline={p}
                lastRun={
                  p.key === "regression"
                    ? dashboard?.eval?.last_regression?.run_at
                    : dashboard?.eval?.last_health_check?.run_at
                }
                loading={runPipeline.isPending && runPipeline.variables === p.key}
                disabled={!isAdmin}
                onRun={() => runPipeline.mutate(p.key)}
                t={t}
              />
            </Col>
          ))}
        </Row>
      </div>
    </Space>
  );
}
