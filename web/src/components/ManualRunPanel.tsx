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
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, formatApiError } from "../api/client";

type PipelineGroup = "main" | "eval";

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

export const MANUAL_PIPELINES: ManualPipelineDef[] = [
  {
    key: "ingestion",
    label: "告警入库",
    summary: "从 Wazuh Indexer 拉取新告警",
    detail: "读取已启用数据源的上次游标，增量同步告警到 alerts 表。",
    effect: "NEW 告警数量上升；入库流水线时间更新",
    where: "运营概览 → 初筛告警（NEW）",
    link: "/",
    group: "main",
    icon: <CloudDownloadOutlined />,
    color: "#1677ff",
  },
  {
    key: "triage",
    label: "初筛分诊",
    summary: "对 NEW 告警打分并决定路由",
    detail: "规则分、画像提示、白名单等；结果写入 triage_results，告警变为 TRIAGED 或 ARCHIVED。",
    effect: "NEW 减少；待聚合告警产生",
    where: "运营概览 → 告警状态分布",
    link: "/",
    group: "main",
    icon: <FilterOutlined />,
    color: "#13c2c2",
  },
  {
    key: "aggregation",
    label: "事件聚合",
    summary: "把告警合并为调查 Event",
    detail: "按主机+用户+类别+24h 窗口合并，生成或更新 events 记录。",
    effect: "「待调查 Event」数量增加",
    where: "事件列表（状态：待调查）",
    link: "/events",
    group: "main",
    icon: <MergeCellsOutlined />,
    color: "#722ed1",
  },
  {
    key: "investigation",
    label: "Agent 调查 (Pro)",
    summary: "AI 深度调查待审 Event（需专业版 License）",
    detail: "调用 LLM + Skill，输出结构化结论。社区版点击将返回 402。",
    effect: "事件详情出现 ReAct 记录",
    where: "事件详情 → ReAct 对话流",
    link: "/license",
    group: "main",
    icon: <RobotOutlined />,
    color: "#eb2f96",
  },
  {
    key: "human_review",
    label: "协查派发 (Pro)",
    summary: "向 IM 发送人工协查问题（需专业版）",
    detail: "企微推送或 Web 协查 inbox。",
    effect: "人工协查页出现待回复请求",
    where: "协查管理",
    link: "/license",
    group: "main",
    icon: <MessageOutlined />,
    color: "#fa8c16",
  },
  {
    key: "defense_assets",
    label: "防御资产沉淀 (Pro)",
    summary: "已结论事件写入判例与建议（需专业版）",
    detail: "生成判例、白名单候选、处置建议等。",
    effect: "防御资产页出现待确认项",
    where: "防御资产",
    link: "/license",
    group: "main",
    icon: <SafetyOutlined />,
    color: "#52c41a",
  },
  {
    key: "regression",
    label: "回归测试 (Pro)",
    summary: "用内置样本校验 Agent 行为（需专业版）",
    detail: "不参与日常告警处理。",
    effect: "评测页显示最新回归通过率",
    where: "评测",
    link: "/license",
    group: "eval",
    icon: <ExperimentOutlined />,
    color: "#597ef7",
  },
  {
    key: "health_check",
    label: "链路探针 (Pro)",
    summary: "端到端自检（需专业版）",
    detail: "模拟探针告警跑通整条链路。",
    effect: "评测页显示 PASS / FAIL",
    where: "评测",
    link: "/license",
    group: "eval",
    icon: <HeartOutlined />,
    color: "#f5222d",
  },
];
const MAIN_FLOW_KEYS = MANUAL_PIPELINES.filter((p) => p.group === "main").map((p) => p.key);

function formatRunResult(key: string, result: Record<string, unknown> | undefined): string {
  if (!result) return "已提交";
  const errors = result.errors;
  if (Array.isArray(errors) && errors.length > 0) {
    return errors.map(String).join("；");
  }
  if (result.skipped_lock) return "调度锁占用，本轮未执行（约 2–5 分钟后重试）";
  if (result.skipped_budget) return "今日调查预算已用完";
  if (result.skipped_not_configured) return "协查通道未配置，已跳过";
  if (result.skipped_disabled) return "功能已关闭（见系统配置）";

  switch (key) {
    case "ingestion": {
      const inserted = Number(result.inserted ?? 0);
      const dup = Number(result.duplicates ?? 0);
      const fetched = Number(result.fetched ?? 0);
      if (fetched === 0 && inserted === 0) {
        return "拉取 0 条（暂无新告警或回溯窗口内无数据，请查看下方「告警入库故障排查」）";
      }
      return `拉取 ${fetched} 条，新增 ${inserted} 条，重复 ${dup} 条`;
    }
    case "triage":
      return `处理 ${result.processed ?? 0} 条`;
    case "aggregation":
      return `处理 ${result.processed ?? 0} 条，新建 Event ${result.events_created ?? 0}，合并 ${result.events_merged ?? 0}`;
    case "investigation":
      return `调查 ${result.processed ?? 0} 个 Event`;
    case "human_review": {
      const cancelled = Number(result.cancelled_obsolete ?? 0);
      const parts = [`下发 ${result.dispatched ?? 0} 条`, `过期 ${result.expired ?? 0} 条`];
      if (cancelled > 0) {
        parts.push(`清理旧单 ${cancelled} 条`);
      }
      return parts.join("，");
    }
    case "defense_assets":
      return `沉淀 ${result.processed ?? 0} 个 Event`;
    case "regression":
      return `通过 ${result.passed ?? 0}/${result.total ?? 0}`;
    case "health_check":
      return `通过 ${result.passed ?? 0}/${result.total ?? 0}`;
    default:
      return "已完成";
  }
}

function formatLastRun(iso: string | null | undefined): string {
  if (!iso) return "从未运行";
  return iso.slice(0, 19).replace("T", " ");
}

function PipelineCard({
  pipeline,
  lastRun,
  loading,
  disabled,
  onRun,
}: {
  pipeline: ManualPipelineDef;
  lastRun?: string | null;
  loading: boolean;
  disabled?: boolean;
  onRun: () => void;
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
            预期效果
          </Tag>
          {pipeline.effect}
        </Typography.Text>
        <Typography.Text style={{ fontSize: 12 }}>
          <Tag color="green" bordered={false}>
            查看位置
          </Tag>
          {pipeline.link ? <Link to={pipeline.link}>{pipeline.where}</Link> : pipeline.where}
        </Typography.Text>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          最近运行：{formatLastRun(lastRun)}
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
        立即运行
      </Button>
    </Card>
  );
}

export default function ManualRunPanel() {
  const qc = useQueryClient();
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
      const def = MANUAL_PIPELINES.find((p) => p.key === key);
      const summary = formatRunResult(key, result);
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

  const mainPipelines = MANUAL_PIPELINES.filter((p) => p.group === "main");
  const evalPipelines = MANUAL_PIPELINES.filter((p) => p.group === "eval");

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="middle">
      {!isAdmin && me && (
        <Alert
          type="warning"
          showIcon
          message="当前账号无管理员权限"
          description="手动运行流水线需要管理员账号（默认 admin）。请退出后使用管理员重新登录。"
        />
      )}

      <Alert
        type="info"
        showIcon
        message="手动运行说明"
        description={
          <>
            系统每 2–5 分钟会自动调度各阶段；此处用于<strong>立即补跑一轮</strong>（默认每轮最多 10
            条）。日常处理请按下方箭头顺序依次执行；若某步显示「处理 0 条」，通常是上一步尚无可用数据。
            详细数字也会出现在浏览器开发者工具 Network 的响应中。
          </>
        }
      />

      <Card title="日常告警处理流程" size="small">
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
          推荐顺序：{MAIN_FLOW_KEYS.map((k) => MANUAL_PIPELINES.find((p) => p.key === k)?.label).join(" → ")}
        </Typography.Paragraph>
      </Card>

      <div>
        <Typography.Title level={5} style={{ marginBottom: 12 }}>
          日常流水线
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
              />
            </Col>
          ))}
        </Row>
      </div>

      <div>
        <Typography.Title level={5} style={{ marginBottom: 12 }}>
          运维自检（不影响真实告警）
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
              />
            </Col>
          ))}
        </Row>
      </div>
    </Space>
  );
}
