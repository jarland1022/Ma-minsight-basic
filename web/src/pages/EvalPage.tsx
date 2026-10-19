import {
  Button,
  Card,
  Col,
  Row,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";
import type {
  HealthCheckRunRow,
  HealthScenarioRow,
  ListResponse,
  Paginated,
  RegressionCaseRow,
  RegressionRunRow,
} from "../types/api";

export default function EvalPage() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [tagFilter, setTagFilter] = useState<string | undefined>();

  const { data: cases } = useQuery<ListResponse<RegressionCaseRow>>({
    queryKey: ["regression-cases", tagFilter],
    queryFn: async () =>
      (await api.get("/regression/cases", { params: tagFilter ? { tag: tagFilter } : {} })).data,
  });

  const { data: runs } = useQuery<Paginated<RegressionRunRow>>({
    queryKey: ["regression-runs"],
    queryFn: async () => (await api.get("/regression/runs")).data,
  });

  const { data: scenarios } = useQuery<ListResponse<HealthScenarioRow>>({
    queryKey: ["health-scenarios"],
    queryFn: async () => (await api.get("/health-checks/scenarios")).data,
  });

  const { data: hcRuns } = useQuery<Paginated<HealthCheckRunRow>>({
    queryKey: ["health-runs"],
    queryFn: async () => (await api.get("/health-checks/runs")).data,
  });

  const runRegression = useMutation({
    mutationFn: () => api.post("/regression/run"),
    onSuccess: (res) => {
      message.success(
        t("evalPage.regressionDone", { passed: res.data.passed, total: res.data.total }),
      );
      qc.invalidateQueries({ queryKey: ["regression-runs"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const runHealth = useMutation({
    mutationFn: () => api.post("/health-checks/run"),
    onSuccess: (res) => {
      message.success(
        t("evalPage.healthDone", { passed: res.data.passed, total: res.data.total }),
      );
      qc.invalidateQueries({ queryKey: ["health-runs"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Typography.Title level={4}>{t("evalPage.title")}</Typography.Title>
      <Typography.Paragraph type="secondary">{t("evalPage.proHint")}</Typography.Paragraph>

      <Row gutter={16}>
        <Col span={12}>
          <Card
            title={t("evalPage.regressionTitle")}
            extra={
              <Button
                type="primary"
                loading={runRegression.isPending}
                onClick={() => runRegression.mutate()}
              >
                {t("evalPage.runRegression")}
              </Button>
            }
          >
            <Table<RegressionRunRow>
              size="small"
              rowKey="id"
              pagination={{ pageSize: 8 }}
              dataSource={runs?.items ?? []}
              columns={[
                {
                  title: t("evalPage.colTime"),
                  dataIndex: "run_at",
                  render: (v: string) => v?.slice(0, 19),
                },
                {
                  title: t("evalPage.colResult"),
                  render: (_, r) => (
                    <Tag color={r.failed === 0 ? "green" : "red"}>
                      {r.passed}/{r.total}
                    </Tag>
                  ),
                },
                { title: t("evalPage.colModel"), dataIndex: "model_name" },
              ]}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card
            title={t("evalPage.healthTitle")}
            extra={
              <Button type="primary" loading={runHealth.isPending} onClick={() => runHealth.mutate()}>
                {t("evalPage.runHealth")}
              </Button>
            }
          >
            <Table<HealthCheckRunRow>
              size="small"
              rowKey="id"
              pagination={{ pageSize: 8 }}
              dataSource={hcRuns?.items ?? []}
              columns={[
                {
                  title: t("evalPage.colTime"),
                  dataIndex: "run_at",
                  render: (v: string) => v?.slice(0, 19),
                },
                {
                  title: t("evalPage.colStatus"),
                  dataIndex: "passed",
                  render: (v) => <Tag color={v ? "green" : "red"}>{v ? "PASS" : "FAIL"}</Tag>,
                },
                { title: t("evalPage.colScenario"), dataIndex: "scenario_id", ellipsis: true },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Tabs
        items={[
          {
            key: "cases",
            label: t("evalPage.tabCases"),
            children: (
              <>
                <Space style={{ marginBottom: 12 }} wrap>
                  {["entity_graph", "refutation", "phase2", "agent"].map((tag) => (
                    <Tag
                      key={tag}
                      color={tagFilter === tag ? "blue" : "default"}
                      style={{ cursor: "pointer" }}
                      onClick={() => setTagFilter(tagFilter === tag ? undefined : tag)}
                    >
                      {tag}
                    </Tag>
                  ))}
                </Space>
                <Table
                  rowKey="id"
                  dataSource={cases?.items ?? []}
                  pagination={{ pageSize: 10 }}
                  columns={[
                    { title: t("evalPage.colName"), dataIndex: "name" },
                    { title: t("evalPage.colExpected"), dataIndex: "expected_verdict" },
                    {
                      title: t("evalPage.colTags"),
                      dataIndex: "tags",
                      render: (v: string[] | undefined) =>
                        (v ?? []).map((x) => <Tag key={x}>{x}</Tag>),
                    },
                    {
                      title: t("evalPage.colSkills"),
                      dataIndex: "expected_skills",
                      render: (v) => (v ?? []).join(", "),
                    },
                    {
                      title: t("evalPage.colActive"),
                      dataIndex: "is_active",
                      render: (v) => (v ? t("evalPage.yes") : t("evalPage.no")),
                    },
                  ]}
                />
              </>
            ),
          },
          {
            key: "scenarios",
            label: t("evalPage.tabScenarios"),
            children: (
              <Table
                rowKey="id"
                dataSource={scenarios?.items ?? []}
                pagination={{ pageSize: 10 }}
                columns={[
                  { title: t("evalPage.colName"), dataIndex: "name" },
                  { title: t("evalPage.colStage"), dataIndex: "expected_stage" },
                  { title: t("evalPage.colDesc"), dataIndex: "description" },
                ]}
              />
            ),
          },
        ]}
      />
    </Space>
  );
}
