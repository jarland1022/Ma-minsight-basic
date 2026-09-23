import { Card, Col, Descriptions, List, Row, Space, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import PageBackHeader from "../components/PageBackHeader";

type TracePayload = {
  event_id?: string;
  closure_retry_count?: number;
  sop?: {
    name?: string;
    recommended_skills?: string[];
    hypothesis_template?: Record<string, unknown>;
  } | null;
  conclusion?: {
    verdict?: string;
    reasoning?: string;
    evidence_closure_score?: number | null;
    refutation_coverage?: number | null;
    closure_passed?: boolean | null;
    closure_checks?: Record<string, unknown> | null;
    hypotheses_evaluated?: unknown[] | null;
    refutation_summary?: string | null;
  } | null;
  messages?: { role: string; content: string; sequence: number }[];
  tool_calls?: { step: number; skill_name: string; output_summary: string; success: boolean }[];
};

export default function TracePage() {
  const { id } = useParams();
  const { data, isLoading } = useQuery<TracePayload>({
    queryKey: ["trace", id],
    queryFn: async () => (await api.get(`/investigations/${id}/trace`)).data,
    enabled: !!id,
  });

  if (isLoading || !data) {
    return <Typography.Text>加载中...</Typography.Text>;
  }

  const closureChecks = data.conclusion?.closure_checks;

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <PageBackHeader
        to={data.event_id ? `/events/${data.event_id}` : "/events"}
        label="返回事件详情"
      />

      {data.conclusion && (
        <Card title="结论与证据闭合度">
          <Typography.Paragraph>
            <Tag color="blue">{data.conclusion.verdict}</Tag>
            {data.conclusion.closure_passed != null && (
              <Tag color={data.conclusion.closure_passed ? "green" : "orange"}>
                闭合 {data.conclusion.closure_passed ? "通过" : "未通过"}
              </Tag>
            )}
            {(data.closure_retry_count ?? 0) > 0 && (
              <Tag>驳回 {data.closure_retry_count} 次</Tag>
            )}
          </Typography.Paragraph>
          <Descriptions column={2} size="small">
            <Descriptions.Item label="闭合度">
              {data.conclusion.evidence_closure_score?.toFixed(2) ?? "—"}
            </Descriptions.Item>
            <Descriptions.Item label="反证覆盖">
              {data.conclusion.refutation_coverage?.toFixed(2) ?? "—"}
            </Descriptions.Item>
          </Descriptions>
          {data.conclusion.refutation_summary && (
            <Typography.Paragraph type="secondary">
              反证摘要：{data.conclusion.refutation_summary}
            </Typography.Paragraph>
          )}
          {closureChecks && (
            <Typography.Paragraph>
              <Typography.Text strong>closure_checks：</Typography.Text>
              <pre style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>
                {JSON.stringify(closureChecks, null, 2)}
              </pre>
            </Typography.Paragraph>
          )}
        </Card>
      )}

      {data.sop?.hypothesis_template && (
        <Card title={`SOP 假设模板 · ${data.sop.name ?? ""}`}>
          <Typography.Paragraph type="secondary">
            推荐 Skill：{(data.sop.recommended_skills ?? []).join(", ")}
          </Typography.Paragraph>
          <pre style={{ whiteSpace: "pre-wrap" }}>
            {JSON.stringify(data.sop.hypothesis_template, null, 2)}
          </pre>
        </Card>
      )}

      <Row gutter={16}>
        <Col span={14}>
          <Card title="ReAct 对话流">
            <List
              dataSource={data.messages ?? []}
              renderItem={(m) => (
                <List.Item>
                  <List.Item.Meta
                    title={<Tag>{m.role}</Tag>}
                    description={<pre style={{ whiteSpace: "pre-wrap" }}>{m.content}</pre>}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col span={10}>
          <Card title="Skill 调用">
            <List
              dataSource={data.tool_calls ?? []}
              renderItem={(t) => (
                <List.Item>
                  <Typography.Text strong>
                    #{t.step} {t.skill_name} {t.success ? "✓" : "✗"}
                  </Typography.Text>
                  <div>{t.output_summary}</div>
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
