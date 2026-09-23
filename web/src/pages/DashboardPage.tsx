import { Alert, Card, Col, Row, Statistic, Table, Typography } from "antd";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, formatApiError } from "../api/client";
import UserGuidePanel from "../components/UserGuidePanel";
import { PAGE_GUIDES, QUICK_START_STEPS } from "../content/userGuide";
import type { NoisyRulesResponse } from "../types/api";

export default function DashboardPage() {
  const { data, isLoading, isError, error, dataUpdatedAt, refetch, isFetching } = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get("/dashboard/summary")).data,
    refetchInterval: 60_000,
  });
  const { data: noisyRules, refetch: refetchNoisy } = useQuery<NoisyRulesResponse>({
    queryKey: ["noisy-rules"],
    queryFn: async () => (await api.get("/dashboard/noisy-rules")).data,
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return <Typography.Text>加载中...</Typography.Text>;
  }

  if (isError || !data) {
    return (
      <Alert
        type="warning"
        showIcon
        message="无法加载仪表盘"
        description={
          <>
            {isError ? formatApiError(error) : "接口未返回数据"}
            <br />
            若长时间停留在此，请尝试退出登录后重新登录；或执行{" "}
            <Typography.Text code>docker compose exec app alembic upgrade head</Typography.Text>
            完成数据库迁移。
          </>
        }
      />
    );
  }

  const evalHealthy = data.eval?.healthy !== false;
  const reg = data.eval?.last_regression;
  const hc = data.eval?.last_health_check;
  const pipeline = data.pipeline_last_run ?? {};
  const pipelineLabels: Record<string, string> = {
    ingestion: "入库",
    triage: "初筛",
    aggregation: "聚合",
    investigation: "Agent 调查",
    human_review: "协查派发",
    defense_assets: "防御资产",
  };

  return (
    <div>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="MA-MinSight 社区版"
        description={
          <>
            免费能力：告警入库 → 初筛 → 聚合 → 事件台 / 技能库。AI Agent、企微协查、防御资产、评测需{" "}
            <Link to="/license">导入专业版 License</Link>。对照说明见仓库{" "}
            <Typography.Text code>docs/community-vs-pro.md</Typography.Text>。
          </>
        }
      />
      <UserGuidePanel guide={PAGE_GUIDES.dashboard} />
      {(data.events?.human_pending ?? 0) > 0 && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message={`您有 ${data.events?.human_pending} 个事件等待协查回复`}
          description={
            <>
              请打开 <Link to="/human-review">人工协查</Link>，用日常语言回答 AI 的问题即可。
              不会写？查看 <Link to="/guide">使用指南</Link> 中的回复示例。
            </>
          }
        />
      )}
      {(data.defense_assets?.disposition_suggested ?? 0) > 0 && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message={`有 ${data.defense_assets?.disposition_suggested} 条处置建议待确认`}
          description={
            <>
              请到 <Link to="/defense-assets">防御资产</Link> 阅读 AI 建议后点「确认」或「拒绝」。
              确认不会自动封 IP 或隔离主机，仅作审批记录。
            </>
          }
        />
      )}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          运营概览
        </Typography.Title>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {isFetching ? "刷新中…" : `更新于 ${new Date(dataUpdatedAt).toLocaleTimeString()}`}
          {" · "}
          <Typography.Link
            onClick={() => {
              refetch();
              refetchNoisy();
            }}
          >
            立即刷新
          </Typography.Link>
        </Typography.Text>
      </div>
      {!evalHealthy && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="评测/探针异常"
          description={
            <>
              {reg && reg.failed > 0 && (
                <div>
                  最近回归：{reg.passed}/{reg.total} 通过（{reg.run_at?.slice(0, 19)}）
                </div>
              )}
              {hc && hc.passed === false && <div>最近链路探针失败</div>}
            </>
          }
        />
      )}
      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Card>
            <Statistic title="待调查 Event" value={data.events?.pending_review ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="协查中" value={data.events?.human_pending ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="今日调查 / 预算"
              value={data.investigations?.today_count ?? 0}
              suffix={`/ ${data.investigations?.daily_budget ?? 0}`}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="待处置建议" value={data.defense_assets?.disposition_suggested ?? 0} />
          </Card>
        </Col>
      </Row>
      <Card style={{ marginTop: 16 }} title="调查成本（今日已完成）">
        <Row gutter={16}>
          <Col span={8}>
            <Statistic title="完成调查数" value={data.investigations?.today_completed ?? 0} />
          </Col>
          <Col span={8}>
            <Statistic
              title="平均 Token / Event"
              value={data.investigations?.avg_tokens_per_event ?? 0}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="平均 Skill 调用"
              value={data.investigations?.avg_skill_calls_per_event ?? 0}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="平均耗时 (秒)"
              value={data.investigations?.avg_duration_seconds ?? 0}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="P95 耗时 (秒)"
              value={data.investigations?.p95_duration_seconds ?? 0}
            />
          </Col>
        </Row>
      </Card>
      {(data.correlation?.events_with_related ?? 0) > 0 && (
        <Card style={{ marginTop: 16 }} title="告警关联">
          <Statistic title="含关联 Event" value={data.correlation?.events_with_related ?? 0} />
        </Card>
      )}
      {(data.supervisor?.audit_total_7d ?? 0) > 0 && (
        <Card style={{ marginTop: 16 }} title="监督审计（近 7 日）">
          <Row gutter={16}>
            <Col span={8}>
              <Statistic title="审计次数" value={data.supervisor?.audit_total_7d ?? 0} />
            </Col>
            <Col span={8}>
              <Statistic title="未通过" value={data.supervisor?.audit_failed_7d ?? 0} />
            </Col>
            <Col span={8}>
              <Statistic
                title="失败率"
                value={(data.supervisor?.audit_failure_rate_7d ?? 0) * 100}
                precision={1}
                suffix="%"
              />
            </Col>
          </Row>
        </Card>
      )}
      <Card style={{ marginTop: 16 }} title="评测健康">
        <Row gutter={16}>
          <Col span={12}>
            <Statistic
              title="最近回归"
              value={reg ? `${reg.passed}/${reg.total}` : "—"}
              valueStyle={{ color: reg && reg.failed > 0 ? "#cf1322" : "#3f8600" }}
            />
          </Col>
          <Col span={12}>
            <Statistic
              title="最近探针"
              value={hc?.passed === false ? "FAIL" : hc ? "PASS" : "—"}
              valueStyle={{ color: hc && hc.passed === false ? "#cf1322" : "#3f8600" }}
            />
          </Col>
        </Row>
      </Card>
      <Card style={{ marginTop: 16 }} title="高噪音规则（近 30 天）">
        <Typography.Paragraph type="secondary">
          {noisyRules?.note ||
            "根据调查结论和处置建议的人工确认/驳回汇总。这里只标出该收紧的 Wazuh 规则，不会自动改规则。"}
        </Typography.Paragraph>
        <Table
          rowKey={(row) => row.rule_id || row.rule_name || "unknown"}
          pagination={false}
          size="small"
          dataSource={noisyRules?.items ?? []}
          locale={{ emptyText: "还没有可排序的规则。请先在「防御资产」确认或拒绝处置建议。" }}
          columns={[
            {
              title: "规则",
              render: (_, row) => (
                <div>
                  <div>{row.rule_name}</div>
                  {row.rule_id && (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {row.rule_id}
                    </Typography.Text>
                  )}
                </div>
              ),
            },
            { title: "告警", dataIndex: "alert_count", width: 72 },
            { title: "事件", dataIndex: "event_count", width: 72 },
            { title: "人工确认误报", dataIndex: "human_confirmed_fp", width: 120 },
            { title: "人工确认攻击", dataIndex: "human_confirmed_attack", width: 120 },
            {
              title: "AI 误报占比",
              dataIndex: "fp_ratio",
              width: 110,
              render: (value: number) => `${Math.round((value ?? 0) * 100)}%`,
            },
            { title: "建议", dataIndex: "suggestion" },
          ]}
        />
      </Card>
      <Card style={{ marginTop: 16 }} title="流水线最近运行（无新数据时先看这里）">
        <Row gutter={[16, 8]}>
          {Object.entries(pipelineLabels).map(([key, label]) => (
            <Col span={8} key={key}>
              <Typography.Text>
                {label}：{" "}
                {pipeline[key] ? (
                  <Typography.Text code>{pipeline[key].slice(0, 19).replace("T", " ")}</Typography.Text>
                ) : (
                  <Typography.Text type="warning">从未运行</Typography.Text>
                )}
              </Typography.Text>
            </Col>
          ))}
        </Row>
        {(pipeline.ingestion == null || data.alerts?.new === 0) && (
          <Alert
            type="info"
            showIcon
            style={{ marginTop: 12 }}
            message="告警不增长？"
            description="确认 Wazuh 数据源已配置且 is_active=true，.env 中 WAZUH_INDEXER_USER/PASSWORD 正确，且入库任务有最近运行时间。"
          />
        )}
        {(data.events?.human_pending ?? 0) > 0 && (
          <Alert
            type="info"
            showIcon
            style={{ marginTop: 12 }}
            message={`${data.events?.human_pending} 个事件在「协查中」`}
            description={
              <>
                请在 <Link to="/human-review">人工协查</Link> 或事件详情页提交回复；AI 复跑后才会变为「已结论」。
              </>
            }
          />
        )}
      </Card>
      <Card style={{ marginTop: 16 }} title="日常处理顺序（非管理员）">
        <ol style={{ marginBottom: 0, paddingLeft: 20 }}>
          {QUICK_START_STEPS.map((step) => (
            <li key={step} style={{ marginBottom: 6 }}>
              {step}
            </li>
          ))}
        </ol>
      </Card>
      <Card style={{ marginTop: 16 }} title="初筛告警">
        <Row gutter={16}>
          <Col span={8}>
            <Statistic title="NEW" value={data.alerts?.new ?? 0} />
          </Col>
          <Col span={8}>
            <Statistic title="TRIAGED" value={data.alerts?.triaged ?? 0} />
          </Col>
          <Col span={8}>
            <Statistic title="ARCHIVED" value={data.alerts?.archived ?? 0} />
          </Col>
        </Row>
      </Card>
    </div>
  );
}
