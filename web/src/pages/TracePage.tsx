import { Card, Col, Descriptions, List, Row, Space, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import PageBackHeader from "../components/PageBackHeader";
import { DispositionGradeTag, EvidenceStrengthTag, VerdictTag } from "../components/VerdictLabels";

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
    recommended_action?: string | null;
    evidence_refs?: string[] | null;
    evidence_strength?: string | null;
    disposition_grade?: string | null;
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
            <VerdictTag verdict={data.conclusion.verdict} />
            <DispositionGradeTag grade={data.conclusion.disposition_grade} />
            <EvidenceStrengthTag strength={data.conclusion.evidence_strength} />
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
          {data.conclusion.recommended_action && (
            <Typography.Paragraph>
              <Typography.Text strong>处置建议：</Typography.Text>
              {data.conclusion.recommended_action}
            </Typography.Paragraph>
          )}
          {(data.conclusion.evidence_refs?.length ?? 0) > 0 && (
            <Typography.Paragraph>
              <Typography.Text strong>证据引用：</Typography.Text>
              {data.conclusion.evidence_refs!.map((ref) => (
                <Tag key={ref}>{ref}</Tag>
              ))}
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
          {data.conclusion.reasoning && (
            <Typography.Paragraph>{data.conclusion.reasoning}</Typography.Paragraph>
          )}
        </Card>
      )}

      <Row gutter={16}>
        <Col span={12}>
          <Card title="消息轨迹">
            <List
              size="small"
              dataSource={data.messages ?? []}
              renderItem={(item) => (
                <List.Item>
                  <Space direction="vertical" style={{ width: "100%" }}>
                    <Tag>{item.role}</Tag>
                    <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}>
                      {item.content}
                    </Typography.Paragraph>
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Skill 调用">
            <List
              size="small"
              dataSource={data.tool_calls ?? []}
              renderItem={(item) => (
                <List.Item>
                  <Space direction="vertical" style={{ width: "100%" }}>
                    <span>
                      #{item.step} <Tag color={item.success ? "green" : "red"}>{item.skill_name}</Tag>
                    </span>
                    <Typography.Text type="secondary">{item.output_summary}</Typography.Text>
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
