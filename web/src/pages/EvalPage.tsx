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
import type {
  HealthCheckRunRow,
  HealthScenarioRow,
  ListResponse,
  Paginated,
  RegressionCaseRow,
  RegressionRunRow,
} from "../types/api";

export default function EvalPage() {
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
      message.success(`回归完成 ${res.data.passed}/${res.data.total}`);
      qc.invalidateQueries({ queryKey: ["regression-runs"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const runHealth = useMutation({
    mutationFn: () => api.post("/health-checks/run"),
    onSuccess: (res) => {
      message.success(`探针完成 ${res.data.passed}/${res.data.total}`);
      qc.invalidateQueries({ queryKey: ["health-runs"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Typography.Title level={4}>评测与链路健康</Typography.Title>

      <Row gutter={16}>
        <Col span={12}>
          <Card
            title="Agent 回归"
            extra={
              <Button type="primary" loading={runRegression.isPending} onClick={() => runRegression.mutate()}>
                运行回归（Mock LLM）
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
                  title: "时间",
                  dataIndex: "run_at",
                  render: (v: string) => v?.slice(0, 19),
                },
                {
                  title: "结果",
                  render: (_, r) => (
                    <Tag color={r.failed === 0 ? "green" : "red"}>
                      {r.passed}/{r.total}
                    </Tag>
                  ),
                },
                { title: "模型", dataIndex: "model_name" },
              ]}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card
            title="链路探针"
            extra={
              <Button type="primary" loading={runHealth.isPending} onClick={() => runHealth.mutate()}>
                运行全部探针
              </Button>
            }
          >
            <Table<HealthCheckRunRow>
              size="small"
              rowKey="id"
              pagination={{ pageSize: 8 }}
              dataSource={hcRuns?.items ?? []}
              columns={[
                { title: "时间", dataIndex: "run_at", render: (v: string) => v?.slice(0, 19) },
                {
                  title: "状态",
                  dataIndex: "passed",
                  render: (v) => <Tag color={v ? "green" : "red"}>{v ? "PASS" : "FAIL"}</Tag>,
                },
                { title: "场景", dataIndex: "scenario_id", ellipsis: true },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Tabs
        items={[
          {
            key: "cases",
            label: "回归用例",
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
                    { title: "名称", dataIndex: "name" },
                    { title: "预期 verdict", dataIndex: "expected_verdict" },
                    {
                      title: "标签",
                      dataIndex: "tags",
                      render: (v: string[] | undefined) =>
                        (v ?? []).map((t) => <Tag key={t}>{t}</Tag>),
                    },
                    {
                      title: "Skills",
                      dataIndex: "expected_skills",
                      render: (v) => (v ?? []).join(", "),
                    },
                    {
                      title: "启用",
                      dataIndex: "is_active",
                      render: (v) => (v ? "是" : "否"),
                    },
                  ]}
                />
              </>
            ),
          },
          {
            key: "scenarios",
            label: "探针场景",
            children: (
              <Table
                rowKey="id"
                dataSource={scenarios?.items ?? []}
                pagination={{ pageSize: 10 }}
                columns={[
                  { title: "名称", dataIndex: "name" },
                  { title: "Stage", dataIndex: "expected_stage" },
                  { title: "说明", dataIndex: "description" },
                ]}
              />
            ),
          },
        ]}
      />
    </Space>
  );
}
