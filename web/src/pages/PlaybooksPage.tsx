import { Card, Input, Select, Space, Table, Tag, Typography } from "antd";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useI18n } from "../i18n/I18nProvider";

type Playbook = {
  id: string;
  name: string;
  domain?: string;
  pack?: string;
  alert_categories: string[];
  mitre_attack: string[];
  nist_csf: string[];
  summary: string;
  investigation_steps: string[];
  runtime_skills: string[];
  human_questions: string[];
  disposition_hints: string[];
  source_skill?: string;
  license?: string;
};

type PlaybookCatalog = {
  total: number;
  curated_count?: number;
  community_count?: number;
  mitre_attack_coverage?: number;
  source?: string;
  community_source?: string;
  community_upstream?: string;
  community_license?: string;
  note?: string;
  domains: string[];
  alert_categories: string[];
  items: Playbook[];
};

type CoverageTechnique = {
  technique_id: string;
  playbook_count: number;
  packs: string[];
  sub_techniques?: { technique_id: string; playbook_count: number }[];
  playbook_ids?: string[];
};

type CoverageTactic = {
  id: string;
  key: string;
  name: string;
  name_zh: string;
  technique_count: number;
  playbook_refs: number;
  techniques: CoverageTechnique[];
};

type AttackCoverage = {
  total_playbooks: number;
  covered_techniques: number;
  max_playbook_count: number;
  tactics: CoverageTactic[];
  pack_filter?: string | null;
};

function intensityClass(count: number, max: number): string {
  if (count <= 0 || max <= 0) return "ms-atk-cell empty";
  const r = count / max;
  if (r >= 0.66) return "ms-atk-cell hot";
  if (r >= 0.33) return "ms-atk-cell mid";
  return "ms-atk-cell low";
}

export default function PlaybooksPage() {
  const { t, lang } = useI18n();
  const [domain, setDomain] = useState<string | undefined>();
  const [category, setCategory] = useState<string | undefined>();
  const [pack, setPack] = useState<string | undefined>();
  const [keyword, setKeyword] = useState("");
  const [techniqueFilter, setTechniqueFilter] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data, isLoading } = useQuery<PlaybookCatalog>({
    queryKey: ["playbooks", domain, category, pack],
    queryFn: async () =>
      (
        await api.get("/playbooks", {
          params: {
            domain: domain || undefined,
            category: category || undefined,
            pack: pack || undefined,
          },
        })
      ).data,
  });

  const { data: coverage, isLoading: coverageLoading } = useQuery<AttackCoverage>({
    queryKey: ["playbooks-coverage", pack],
    queryFn: async () =>
      (await api.get("/playbooks/coverage", { params: { pack: pack || undefined } })).data,
  });

  const filtered = useMemo(() => {
    let items = data?.items ?? [];
    if (techniqueFilter) {
      const techId = techniqueFilter.toUpperCase();
      items = items.filter((item) =>
        item.mitre_attack.some((id) => {
          const u = id.toUpperCase();
          return (
            u === techId ||
            u.startsWith(`${techId}.`) ||
            (techId.includes(".") && u === techId.split(".")[0])
          );
        }),
      );
    }
    const q = keyword.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (item) =>
        item.name.toLowerCase().includes(q) ||
        item.id.toLowerCase().includes(q) ||
        item.summary.toLowerCase().includes(q) ||
        (item.source_skill || "").toLowerCase().includes(q) ||
        item.mitre_attack.some((id) => id.toLowerCase().includes(q)),
    );
  }, [data?.items, keyword, techniqueFilter]);

  const selected = filtered.find((item) => item.id === selectedId) ?? filtered[0] ?? null;
  const maxCount = coverage?.max_playbook_count ?? 1;

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Card>
        <Typography.Title level={4} style={{ marginTop: 0 }}>
          {t("playbooks.title")}
        </Typography.Title>
        <Typography.Paragraph type="secondary">
          {data?.note || t("playbooks.intro")}
        </Typography.Paragraph>
        <Space wrap>
          <Typography.Text>
            {t("playbooks.totalLine", {
              total: data?.total ?? 0,
              curated: data?.curated_count ?? "—",
              community: data?.community_count ?? "—",
            })}
          </Typography.Text>
          {typeof data?.mitre_attack_coverage === "number" ? (
            <Tag color="blue">
              {t("playbooks.attackTech", { count: data.mitre_attack_coverage })}
            </Tag>
          ) : null}
          {data?.community_license ? <Tag>{data.community_license}</Tag> : null}
          <Select
            allowClear
            placeholder={t("playbooks.packPlaceholder")}
            style={{ width: 160 }}
            value={pack}
            onChange={(v) => {
              setPack(v);
              setTechniqueFilter(null);
            }}
            options={[
              { value: "curated", label: t("playbooks.packCurated") },
              { value: "community", label: t("playbooks.packCommunity") },
            ]}
          />
          <Select
            allowClear
            placeholder={t("playbooks.domainPlaceholder")}
            style={{ width: 160 }}
            value={domain}
            onChange={setDomain}
            options={(data?.domains ?? []).map((d) => ({ value: d, label: d }))}
          />
          <Select
            allowClear
            placeholder={t("playbooks.categoryPlaceholder")}
            style={{ width: 200 }}
            value={category}
            onChange={setCategory}
            options={(data?.alert_categories ?? []).map((c) => ({ value: c, label: c }))}
          />
          <Input.Search
            allowClear
            placeholder={t("playbooks.searchPlaceholder")}
            style={{ width: 240 }}
            onSearch={setKeyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
        </Space>
      </Card>

      <Card
        title={t("playbooks.coverageTitle")}
        loading={coverageLoading}
        extra={
          <Space size="middle">
            <Typography.Text type="secondary">
              {t("playbooks.coverageStats", {
                tech: coverage?.covered_techniques ?? 0,
                books: coverage?.total_playbooks ?? 0,
              })}
            </Typography.Text>
            {techniqueFilter ? (
              <Tag
                closable
                color="blue"
                onClose={() => setTechniqueFilter(null)}
                style={{ marginInlineEnd: 0 }}
              >
                {t("playbooks.filterTag", { id: techniqueFilter })}
              </Tag>
            ) : (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {t("playbooks.clickHint")}
              </Typography.Text>
            )}
          </Space>
        }
      >
        <div className="ms-atk-board" role="list">
          {(coverage?.tactics ?? []).map((tactic) => {
            const primary = lang === "zh" ? tactic.name_zh : tactic.name;
            const secondary = lang === "zh" ? tactic.name : tactic.name_zh;
            return (
              <div key={tactic.key} className="ms-atk-col" role="listitem">
                <div className="ms-atk-col-head">
                  <div className="ms-atk-col-title">{primary}</div>
                  <div className="ms-atk-col-sub">
                    {secondary} · {tactic.technique_count}
                  </div>
                </div>
                <div className="ms-atk-col-body">
                  {tactic.techniques.length === 0 ? (
                    <div className="ms-atk-gap">{t("playbooks.noCoverage")}</div>
                  ) : (
                    tactic.techniques.map((tech) => (
                      <button
                        key={tech.technique_id}
                        type="button"
                        className={`${intensityClass(tech.playbook_count, maxCount)}${
                          techniqueFilter === tech.technique_id ? " active" : ""
                        }`}
                        title={t("playbooks.playbookCount", {
                          id: tech.technique_id,
                          count: tech.playbook_count,
                        })}
                        onClick={() =>
                          setTechniqueFilter((prev) =>
                            prev === tech.technique_id ? null : tech.technique_id,
                          )
                        }
                      >
                        <span className="ms-atk-id">{tech.technique_id}</span>
                        <span className="ms-atk-n">{tech.playbook_count}</span>
                      </button>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <div className="ms-atk-legend">
          <span>{t("playbooks.density")}</span>
          <span className="ms-atk-cell low legend">{t("playbooks.densityLow")}</span>
          <span className="ms-atk-cell mid legend">{t("playbooks.densityMid")}</span>
          <span className="ms-atk-cell hot legend">{t("playbooks.densityHigh")}</span>
        </div>
      </Card>

      <Space align="start" style={{ width: "100%" }} size="large">
        <Card
          title={
            techniqueFilter
              ? t("playbooks.listTitleFiltered", { id: techniqueFilter })
              : t("playbooks.listTitle")
          }
          style={{ flex: 1, minWidth: 0 }}
          loading={isLoading}
        >
          <Table<Playbook>
            rowKey="id"
            size="small"
            pagination={{ pageSize: 12 }}
            dataSource={filtered}
            rowClassName={(row) => (row.id === selected?.id ? "ant-table-row-selected" : "")}
            onRow={(row) => ({
              onClick: () => setSelectedId(row.id),
              style: { cursor: "pointer" },
            })}
            columns={[
              { title: t("playbooks.colName"), dataIndex: "name" },
              {
                title: t("playbooks.colPack"),
                dataIndex: "pack",
                width: 100,
                render: (p: string | undefined) =>
                  p === "community" ? (
                    <Tag color="cyan">{t("playbooks.tagCommunity")}</Tag>
                  ) : (
                    <Tag color="geekblue">{t("playbooks.tagCurated")}</Tag>
                  ),
              },
              { title: t("playbooks.colDomain"), dataIndex: "domain", width: 110 },
              {
                title: t("playbooks.colCategory"),
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

        <Card title={selected?.name || t("playbooks.detailTitle")} style={{ width: 420 }}>
          {!selected ? (
            <Typography.Text type="secondary">{t("playbooks.selectHint")}</Typography.Text>
          ) : (
            <Space direction="vertical" style={{ width: "100%" }}>
              <Typography.Text type="secondary">{selected.id}</Typography.Text>
              {selected.pack === "community" ? (
                <Tag color="cyan">
                  {t("playbooks.packCommunity")} · {selected.license || "Apache-2.0"}
                </Tag>
              ) : (
                <Tag color="geekblue">{t("playbooks.packCurated")}</Tag>
              )}
              <Typography.Paragraph>{selected.summary}</Typography.Paragraph>
              <div>
                <Typography.Text strong>{t("playbooks.bindCategories")}</Typography.Text>
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
                    <Tag
                      color="blue"
                      key={c}
                      style={{ cursor: "pointer" }}
                      onClick={() => setTechniqueFilter(c.split(".")[0])}
                    >
                      {c}
                    </Tag>
                  ))}
                  {selected.nist_csf.map((c) => (
                    <Tag key={c}>{c}</Tag>
                  ))}
                </div>
              </div>
              <div>
                <Typography.Text strong>{t("playbooks.steps")}</Typography.Text>
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
                <Typography.Text strong>{t("playbooks.humanQuestions")}</Typography.Text>
                <ul style={{ paddingLeft: 18, marginBottom: 0 }}>
                  {selected.human_questions.map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </ul>
              </div>
              {selected.source_skill ? (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {t("playbooks.upstreamSkill", { skill: selected.source_skill })}
                </Typography.Text>
              ) : null}
            </Space>
          )}
        </Card>
      </Space>
    </Space>
  );
}
