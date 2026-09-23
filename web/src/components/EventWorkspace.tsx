import { Card, Col, Empty, Row, Tag, Typography } from "antd";
import type {
  AlertDetailRow,
  EntityContextSnapshot,
  EntityGraphEdge,
  EntityGraphNode,
  HypothesisTemplate,
  InvestigationRow,
  MatchedPlaybook,
} from "../types/api";

const SKILL_LABEL: Record<string, string> = {
  query_asset: "核对该 IP/主机是否为已知资产、扫描器或值班例外",
  query_threat_intel: "查源地址是否被威胁情报标为恶意",
  query_entity_graph: "沿实体关系看它还连到哪些主机、账号或业务系统",
  query_history_alerts: "看同一实体近期是否还有同类告警",
};

const ENTITY_LABEL: Record<string, string> = {
  ip: "IP",
  host: "主机",
  user: "账号",
  domain: "域名",
};

type FollowUp = { key: string; text: string };

type Stage = { key: string; title: string; items: string[] };

function nodeId(type: string, key: string) {
  return `${type}:${key}`;
}

function entityLabel(type: string, key: string, display?: string | null) {
  const kind = ENTITY_LABEL[type] || type;
  return display ? `${kind} ${display}` : `${kind} ${key}`;
}

function buildStages(alerts: AlertDetailRow[], snapshot?: EntityContextSnapshot | null): Stage[] {
  const sources = unique(alerts.map((row) => row.src_ip).filter(Boolean) as string[]);
  const hosts = unique(
    alerts.map((row) => row.host_name).filter(Boolean) as string[],
  );
  const users = unique(alerts.map((row) => row.user_name).filter(Boolean) as string[]);
  const related = (snapshot?.edges ?? [])
    .map((edge) => `${ENTITY_LABEL[edge.to_type] || edge.to_type} ${edge.to_key}（${edge.relation_type}）`)
    .filter((label, index, all) => all.indexOf(label) === index)
    .slice(0, 6);

  const stages: Stage[] = [
    { key: "source", title: "来源", items: sources.length ? sources : ["未记录源地址"] },
    { key: "host", title: "落点主机", items: hosts.length ? hosts : ["未记录主机"] },
  ];
  if (users.length) {
    stages.push({ key: "user", title: "涉及账号", items: users });
  }
  if (related.length) {
    stages.push({ key: "related", title: "关联扩展", items: related });
  }
  return stages;
}

function unique(values: string[]) {
  return values.filter((value, index) => values.indexOf(value) === index);
}

function buildFollowUps(investigation?: InvestigationRow | null): FollowUp[] {
  const items: FollowUp[] = [];
  const query = investigation?.conclusion?.human_query?.trim();
  if (query) {
    items.push({ key: "human", text: query });
  }

  const checks = investigation?.conclusion?.closure_checks;
  const missing = Array.isArray(checks?.missing_skills) ? (checks.missing_skills as string[]) : [];
  for (const skill of missing) {
    items.push({
      key: `skill-${skill}`,
      text: SKILL_LABEL[skill] || `补充调查：${skill}`,
    });
  }

  const template = investigation?.hypothesis_template;
  const hasConclusion = Boolean(investigation?.conclusion);
  const evaluatedRows = investigation?.conclusion?.hypotheses_evaluated ?? [];
  if (hasConclusion && evaluatedRows.length === 0 && investigation?.conclusion?.closure_passed === false) {
    items.push({ key: "hyp-missing", text: "结论未记录「真实攻击 / 误报」假设的评估结果" });
  }
  for (const hypothesis of template?.default_hypotheses ?? []) {
    if (!hypothesis.id || !hypothesis.label || evaluatedRows.length === 0) continue;
    const evaluated = evaluatedRows.some(
      (row) => row && typeof row === "object" && String((row as { hypothesis_id?: string }).hypothesis_id || "") === hypothesis.id,
    );
    if (!evaluated) {
      items.push({
        key: `hyp-${hypothesis.id}`,
        text: `假设「${hypothesis.label}」尚未在结论中显式评估`,
      });
    }
  }
  for (const hint of template?.refuting_hints ?? []) {
    if (hint.skill && missing.includes(hint.skill) && hint.description) {
      items.push({ key: `refute-${hint.id || hint.description}`, text: `反证尚未覆盖：${hint.description}` });
    }
  }

  if (
    investigation?.conclusion &&
    investigation.conclusion.closure_passed === false &&
    (investigation.conclusion.refutation_coverage ?? 1) < 0.5
  ) {
    items.push({
      key: "refutation",
      text: "反证覆盖不足：确认攻击前需要再查一条能否定攻击的证据（资产归属或正常业务关系）",
    });
  }

  return items.filter((item, index, all) => all.findIndex((other) => other.text === item.text) === index).slice(0, 6);
}

function closureLines(investigation?: InvestigationRow | null, template?: HypothesisTemplate | null) {
  const conclusion = investigation?.conclusion;
  if (!conclusion) {
    return [] as { key: string; ok: boolean | null; text: string }[];
  }
  const checks = conclusion.closure_checks ?? {};
  const missing = Array.isArray(checks.missing_skills) ? (checks.missing_skills as string[]) : [];
  const lines: { key: string; ok: boolean | null; text: string }[] = [];

  if (conclusion.closure_passed != null) {
    lines.push({
      key: "overall",
      ok: conclusion.closure_passed,
      text: conclusion.closure_passed ? "证据闭合校验通过" : "证据闭合校验未通过",
    });
  }
  if (conclusion.evidence_closure_score != null) {
    lines.push({
      key: "score",
      ok: conclusion.evidence_closure_score >= 0.6,
      text: `闭合度 ${conclusion.evidence_closure_score.toFixed(2)}`,
    });
  }
  if (conclusion.refutation_coverage != null) {
    lines.push({
      key: "refute",
      ok: conclusion.refutation_coverage >= 0.5,
      text: `反证覆盖 ${conclusion.refutation_coverage.toFixed(2)}`,
    });
  }
  if (missing.length) {
    lines.push({
      key: "missing",
      ok: false,
      text: `未调用：${missing.map((skill) => SKILL_LABEL[skill] || skill).join("；")}`,
    });
  }
  for (const hint of template?.refuting_hints ?? []) {
    if (!hint.description) continue;
    const missingSkill = Boolean(hint.skill && missing.includes(hint.skill));
    lines.push({
      key: `hint-${hint.id || hint.description}`,
      ok: missingSkill ? false : null,
      text: `反证线索：${hint.description}`,
    });
  }
  return lines;
}

function layoutNodes(nodes: EntityGraphNode[], edges: EntityGraphEdge[], seedType?: string | null, seedKey?: string | null) {
  const byId = new Map(nodes.map((node) => [nodeId(node.entity_type, node.entity_key), node]));
  const neighbors = new Map<string, string[]>();
  for (const edge of edges) {
    const from = nodeId(edge.from_type, edge.from_key);
    const to = nodeId(edge.to_type, edge.to_key);
    neighbors.set(from, [...(neighbors.get(from) ?? []), to]);
    neighbors.set(to, [...(neighbors.get(to) ?? []), from]);
    if (!byId.has(from)) {
      byId.set(from, { entity_type: edge.from_type, entity_key: edge.from_key });
    }
    if (!byId.has(to)) {
      byId.set(to, { entity_type: edge.to_type, entity_key: edge.to_key });
    }
  }

  const seed = seedType && seedKey ? nodeId(seedType, seedKey) : byId.keys().next().value;
  const depth = new Map<string, number>();
  if (seed && byId.has(seed)) {
    const queue = [seed];
    depth.set(seed, 0);
    while (queue.length) {
      const current = queue.shift()!;
      for (const next of neighbors.get(current) ?? []) {
        if (!depth.has(next)) {
          depth.set(next, (depth.get(current) ?? 0) + 1);
          queue.push(next);
        }
      }
    }
  }
  for (const id of byId.keys()) {
    if (!depth.has(id)) depth.set(id, 99);
  }

  const reached = [...depth.values()].filter((level) => level < 99);
  const orphanColumn = (reached.length ? Math.max(...reached) : -1) + 1;
  const columns = new Map<number, string[]>();
  for (const [id, level] of depth) {
    const bucket = level === 99 ? orphanColumn : level;
    columns.set(bucket, [...(columns.get(bucket) ?? []), id]);
  }

  const colWidth = 180;
  const rowHeight = 72;
  const positions = new Map<string, { x: number; y: number }>();
  const orderedCols = [...columns.keys()].sort((a, b) => a - b);
  orderedCols.forEach((col, colIndex) => {
    const ids = columns.get(col) ?? [];
    ids.forEach((id, rowIndex) => {
      positions.set(id, { x: 24 + colIndex * colWidth, y: 28 + rowIndex * rowHeight });
    });
  });

  const height = Math.max(120, ...[...positions.values()].map((pos) => pos.y + 56));
  const width = Math.max(360, 48 + orderedCols.length * colWidth);
  return { byId, positions, edges, width, height, seed };
}

export default function EventWorkspace({
  alerts,
  snapshot,
  investigation,
  playbooks,
}: {
  alerts: AlertDetailRow[];
  snapshot?: EntityContextSnapshot | null;
  investigation?: InvestigationRow | null;
  playbooks?: MatchedPlaybook[] | null;
}) {
  const stages = buildStages(alerts, snapshot);
  const followUps = buildFollowUps(investigation);
  const checks = closureLines(investigation, investigation?.hypothesis_template);
  const graph = layoutNodes(
    snapshot?.nodes ?? [],
    snapshot?.edges ?? [],
    snapshot?.seed_entity_type,
    snapshot?.seed_entity_key,
  );
  const hasGraph = (snapshot?.nodes?.length ?? 0) > 0 || (snapshot?.edges?.length ?? 0) > 0;
  const activePlaybook = playbooks?.[0];

  return (
    <Card title="事件工作台">
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        同一页看清攻击从哪来、落到哪、证据是否闭合，以及还缺哪一步调查。
      </Typography.Paragraph>
      {activePlaybook && (
        <Card size="small" type="inner" title={`本次调查剧本：${activePlaybook.name}`} style={{ marginBottom: 16 }}>
          <Typography.Paragraph style={{ marginBottom: 8 }}>{activePlaybook.summary}</Typography.Paragraph>
          <div style={{ marginBottom: 8 }}>
            {(activePlaybook.mitre_attack ?? []).map((id) => (
              <Tag color="blue" key={id}>
                {id}
              </Tag>
            ))}
            {(activePlaybook.runtime_skills ?? []).map((skill) => (
              <Tag key={skill}>{skill}</Tag>
            ))}
          </div>
          {(activePlaybook.investigation_steps?.length ?? 0) > 0 && (
            <ul style={{ paddingLeft: 18, marginBottom: 0 }}>
              {activePlaybook.investigation_steps!.slice(0, 4).map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ul>
          )}
        </Card>
      )}
      {investigation?.hypothesis_template?.investigation_intent && (
        <Typography.Paragraph>{investigation.hypothesis_template.investigation_intent}</Typography.Paragraph>
      )}

      <Typography.Title level={5}>事件过程</Typography.Title>
      <Row gutter={[12, 12]}>
        {stages.map((stage, index) => (
          <Col key={stage.key} xs={24} md={12} lg={6}>
            <Card size="small" title={`${index + 1}. ${stage.title}`}>
              {stage.items.map((item) => (
                <div key={item}>
                  <Tag style={{ marginBottom: 6 }}>{item}</Tag>
                </div>
              ))}
            </Card>
          </Col>
        ))}
      </Row>

      <Typography.Title level={5} style={{ marginTop: 20 }}>
        实体关系
      </Typography.Title>
      {hasGraph ? (
        <div style={{ overflowX: "auto" }}>
          <svg width={graph.width} height={graph.height} role="img" aria-label="实体关系图">
            {graph.edges.map((edge) => {
              const from = graph.positions.get(nodeId(edge.from_type, edge.from_key));
              const to = graph.positions.get(nodeId(edge.to_type, edge.to_key));
              if (!from || !to) return null;
              return (
                <g key={`${edge.from_type}${edge.from_key}${edge.to_type}${edge.to_key}${edge.relation_type}`}>
                  <line x1={from.x + 70} y1={from.y + 16} x2={to.x} y2={to.y + 16} stroke="#bfbfbf" />
                  <text x={(from.x + to.x) / 2 + 20} y={(from.y + to.y) / 2 + 8} fontSize="11" fill="#8c8c8c">
                    {edge.relation_type}
                  </text>
                </g>
              );
            })}
            {[...graph.positions.entries()].map(([id, pos]) => {
              const node = graph.byId.get(id);
              if (!node) return null;
              const isSeed = id === graph.seed;
              return (
                <g key={id}>
                  <rect
                    x={pos.x}
                    y={pos.y}
                    width="150"
                    height="36"
                    rx="6"
                    fill={isSeed ? "#fff7e6" : "#f6ffed"}
                    stroke={isSeed ? "#fa8c16" : "#52c41a"}
                  />
                  <text x={pos.x + 8} y={pos.y + 23} fontSize="12" fill="#262626">
                    {entityLabel(node.entity_type, node.entity_key, node.display_name).slice(0, 22)}
                  </text>
                </g>
              );
            })}
          </svg>
          {snapshot?.summary && (
            <Typography.Paragraph type="secondary">{snapshot.summary}</Typography.Paragraph>
          )}
        </div>
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={snapshot?.summary || "调查开始时没有可展示的实体关系"}
        />
      )}

      <Typography.Title level={5}>证据闭合</Typography.Title>
      {checks.length ? (
        <ul style={{ paddingLeft: 18, marginBottom: 0 }}>
          {checks.map((line) => (
            <li key={line.key}>
              {line.ok === true && <Tag color="green">已覆盖</Tag>}
              {line.ok === false && <Tag color="orange">缺口</Tag>}
              {line.text}
            </li>
          ))}
        </ul>
      ) : (
        <Typography.Text type="secondary">调查尚未给出闭合校验结果。</Typography.Text>
      )}

      <Typography.Title level={5} style={{ marginTop: 20 }}>
        还可以追问
      </Typography.Title>
      {followUps.length ? (
        <ul style={{ paddingLeft: 18, marginBottom: 0 }}>
          {followUps.map((item) => (
            <li key={item.key}>{item.text}</li>
          ))}
        </ul>
      ) : (
        <Typography.Text type="secondary">当前结论没有列出待补充问题。</Typography.Text>
      )}
    </Card>
  );
}
