import { Card, Input, Select, Space, Table, Tag, Typography } from "antd";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

type Playbook = {
  id: string;
  name: string;
  domain?: string;
  alert_categories: string[];
  mitre_attack: string[];
  nist_csf: string[];
  summary: string;
  investigation_steps: string[];
  runtime_skills: string[];
  human_questions: string[];
  disposition_hints: string[];
};

type PlaybookCatalog = {
  total: number;
  source?: string;
  note?: string;
  domains: string[];
  alert_categories: string[];
  items: Playbook[];
};

export default function PlaybooksPage() {
  const [domain, setDomain] = useState<string | undefined>();
  const [category, setCategory] = useState<string | undefined>();
  const [keyword, setKeyword] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data, isLoading } = useQuery<PlaybookCatalog>({
    queryKey: ["playbooks", domain, category],
    queryFn: async () =>
      (
        await api.get("/playbooks", {
          params: { domain: domain || undefined, category: category || undefined },
        })
      ).data,
  });

  const filtered = useMemo(() => {
    const items = data?.items ?? [];
    const q = keyword.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (item) =>
        item.name.toLowerCase().includes(q) ||
        item.id.toLowerCase().includes(q) ||
        item.summary.toLowerCase().includes(q) ||
        item.mitre_attack.some((t) => t.toLowerCase().includes(q)),
    );
  }, [data?.items, keyword]);

  const selected = filtered.find((item) => item.id === selectedId) ?? filtered[0] ?? null;

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Card>
        <Typography.Title level={4} style={{ marginTop: 0 }}>
          技能库 / 调查剧本
        </Typography.Title>
        <Typography.Paragraph type="secondary">
          {data?.note ||
            "精选防御向调查剧本。调查时会按告警类别自动注入 Agent 提示词；这里展示产品覆盖的场景与 ATT&CK 映射。"}
        </Typography.Paragraph>
        <Space wrap>
          <Typography.Text>共 {data?.total ?? 0} 条</Typography.Text>
          <Select
            allowClear
            placeholder="领域"
            style={{ width: 160 }}
            value={domain}
            onChange={setDomain}
            options={(data?.domains ?? []).map((d) => ({ value: d, label: d }))}
          />
          <Select
            allowClear
            placeholder="告警类别"
            style={{ width: 200 }}
            value={category}
            onChange={setCategory}
            options={(data?.alert_categories ?? []).map((c) => ({ value: c, label: c }))}
          />
          <Input.Search
            allowClear
            placeholder="搜索名称 / ATT&CK"
            style={{ width: 240 }}
            onSearch={setKeyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
        </Space>
      </Card>

      <Space align="start" style={{ width: "100%" }} size="large">
        <Card title="剧本列表" style={{ flex: 1, minWidth: 0 }} loading={isLoading}>
          <Table<Playbook>
            rowKey="id"
            size="small"
            pagination={{ pageSize: 10 }}
            dataSource={filtered}
            rowClassName={(row) => (row.id === selected?.id ? "ant-table-row-selected" : "")}
            onRow={(row) => ({
              onClick: () => setSelectedId(row.id),
              style: { cursor: "pointer" },
            })}
            columns={[
              { title: "名称", dataIndex: "name" },
              { title: "领域", dataIndex: "domain", width: 100 },
              {
                title: "类别",
                dataIndex: "alert_categories",
                render: (cats: string[]) =>
                  cats.filter((c) => c !== "*").slice(0, 2).map((c) => <Tag key={c}>{c}</Tag>),
              },
              {
                title: "ATT&CK",
                dataIndex: "mitre_attack",
                render: (ids: string[]) => ids.slice(0, 3).map((id) => <Tag key={id}>{id}</Tag>),
              },
            ]}
          />
        </Card>

        <Card title={selected?.name || "剧本详情"} style={{ width: 420 }}>
          {!selected ? (
            <Typography.Text type="secondary">选择左侧剧本查看详情</Typography.Text>
          ) : (
            <Space direction="vertical" style={{ width: "100%" }}>
              <Typography.Text type="secondary">{selected.id}</Typography.Text>
              <Typography.Paragraph>{selected.summary}</Typography.Paragraph>
              <div>
                <Typography.Text strong>绑定类别</Typography.Text>
                <div style={{ marginTop: 6 }}>
                  {selected.alert_categories.map((c) => (
                    <Tag key={c}>{c}</Tag>
                  ))}
                </div>
              </div>
              <div>
                <Typography.Text strong>ATT&CK / NIST</Typography.Text>
                <div style={{ marginTop: 6 }}>
                  {selected.mitre_attack.map((c) => (
                    <Tag color="blue" key={c}>
                      {c}
                    </Tag>
                  ))}
                  {selected.nist_csf.map((c) => (
                    <Tag key={c}>{c}</Tag>
                  ))}
                </div>
              </div>
              <div>
                <Typography.Text strong>调查要点</Typography.Text>
                <ul style={{ paddingLeft: 18, marginBottom: 0 }}>
                  {selected.investigation_steps.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ul>
              </div>
              <div>
                <Typography.Text strong>Runtime Skill</Typography.Text>
                <div style={{ marginTop: 6 }}>
                  {selected.runtime_skills.map((s) => (
                    <Tag color="green" key={s}>
                      {s}
                    </Tag>
                  ))}
                </div>
              </div>
              <div>
                <Typography.Text strong>协查问题示例</Typography.Text>
                <ul style={{ paddingLeft: 18, marginBottom: 0 }}>
                  {selected.human_questions.map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </ul>
              </div>
            </Space>
          )}
        </Card>
      </Space>
    </Space>
  );
}
