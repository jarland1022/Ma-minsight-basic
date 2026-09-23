# MA-MinSight 阶段二增强清单

> 基于 Loki《从 AI 工具到安全运营智能体：SOC 的 AI+Native 转型实践》与当前代码库（`app/`、`web/`、`alembic/`）对照编制。  
> 目标：在**不推翻现有单 Agent + Skill 架构**前提下，补齐实体关联推理、假设/反证模板、外置终止判定、调查监督与成本可观测性。

**文档版本**：0.1  
**适用基线**：Alembic `011_config_descriptions_zh` 及之后  
**原则**：增量迁移、Feature Flag（`system_config`）、先规则后 LLM

---

## 一、阶段二总览

### 1.1 与现架构的关系

```text
【已有 · 阶段一】
Wazuh → 入库 → 规则初筛 → 事件聚合 → ReAct 调查(3 Skills) → 协查 → 防御资产

【阶段二 · 增量】
         ↓ 实体关系图 Skill
         ↓ 结构化假设 SOP
         ↓ 结论前外置校验（证据闭合度 / 反证覆盖）
         ↓ 监督审计记录 + Token 成本看板
         ↓ （可选）处置推演 Skill
```

### 1.2 优先级定义

| 级别 | 含义 | 建议周期 |
|------|------|----------|
| **P0** | 直接提升调查质量，改动可控 | 1–2 个迭代 |
| **P1** | 可靠性 / 成本 / 运营闭环 | 2–3 个迭代 |
| **P2** | 平台化、对接外部系统 | 按需 |

### 1.3 工作包一览

| ID | 工作包 | 优先级 | 新表 | 新 Skill | 核心配置 |
|----|--------|--------|------|----------|----------|
| EP-01 | 实体关系与关联推理 | P0 | `entity_relations` | `query_entity_graph` | `entity.*` |
| EP-02 | 结构化假设模板 SOP | P0 | —（扩列） | — | `investigation.hypothesis_*` |
| EP-03 | 外置终止与证据闭合度 | P0 | —（扩列） | `submit_conclusion` 增强 | `investigation.closure_*` |
| EP-04 | 调查监督审计 | P1 | `investigation_audits` | —（服务层） | `investigation.supervisor_*` |
| EP-05 | 初筛智能化与成本看板 | P1 | — | — | `triage.*` / `investigation.metrics_*` |
| EP-06 | 告警关联扩线 | P1 | —（扩列） | `query_correlated_alerts` | `investigation.correlation_*` |
| EP-07 | 处置推演（只读） | P2 | `disposition_simulations` | `simulate_disposition` | `disposition.*` |
| EP-08 | 评测与回归扩展 | P1 | — | — | `eval.*` |
| EP-09 | 工具网关（可选） | P2 | `tool_gateway_credentials` | 统一 Skill 底座 | `tools.gateway_*` |

---

## 二、P0 工作包详单

### EP-01 实体关系与关联推理

**目标**：解决 PDF 中「孤立告警 vs 实体关联」问题——IP → 用户 → 部门 → 主机 → 业务交互链。

#### 2.1.1 数据库变更

**迁移**：`012_entity_relations.py`

**新建表 `entity_relations`**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `from_entity_type` | enum EntityType | ip / host / user / domain |
| `from_entity_key` | varchar(256) | |
| `to_entity_type` | enum EntityType | |
| `to_entity_key` | varchar(256) | |
| `relation_type` | varchar(64) | 如 `owns`、`manages`、`connects_to`、`same_department`、`business_peer` |
| `confidence` | float | 0–1，人工/导入来源可信度 |
| `source` | varchar(64) | `seed` / `cmdb` / `investigation` / `manual` |
| `metadata` | JSONB | 备注、有效期、证据链接 |
| `valid_from` / `valid_until` | timestamptz | 可选 |
| `created_at` | timestamptz | |

**索引**：

- `(from_entity_type, from_entity_key)`
- `(to_entity_type, to_entity_key)`
- `(relation_type)`

**扩列 `entity_profiles.metadata`（JSONB，已有）**

建议规范字段（不强制 DDL，由 seed/导入写入）：

```json
{
  "department": "采购部",
  "business_systems": ["采购系统"],
  "peer_hosts": ["finance-server-01"],
  "owner_user": "zhangsan"
}
```

**扩列 `events`（可选，P1 可并 EP-06）**

| 字段 | 类型 | 说明 |
|------|------|------|
| `entity_context_snapshot` | JSONB | 调查开始时冻结的关联子图，供审计回放 |

#### 2.1.2 Skill

**新建 `query_entity_graph`**（`app/skills/query_entity_graph.py`）

| 项 | 内容 |
|----|------|
| 名称 | `query_entity_graph` |
| 入参 | `seed_entity_type`, `seed_entity_key`, `max_hops`(默认 2), `relation_types`(可选) |
| 出参 | 节点列表 + 边列表 + 自然语言摘要（如「张三(IP) → 采购部 → web-server-01 ↔ finance-server-01」） |
| 数据源 | `entity_relations` + `entity_profiles` + `on_duty_knowledge` |
| 注册 | `app/skills/bootstrap.py` |

**修改 `query_asset`**

- 返回中增加 `related_entities[]`（1-hop 邻居摘要）
- 不改变现有参数，向后兼容

#### 2.1.3 配置项（`system_config` + seed 迁移）

| Key | 默认 | 说明 |
|-----|------|------|
| `entity.graph_enabled` | `true` | 是否启用图查询 Skill |
| `entity.graph_max_hops` | `2` | BFS 最大跳数 |
| `entity.graph_max_nodes` | `30` | 单次返回节点上限 |
| `entity.relation_ttl_days` | `365` | 自动过期（可选任务） |

#### 2.1.4 代码触点

| 模块 | 改动 |
|------|------|
| `app/models/entity.py` | 新增 `EntityRelation` 模型 |
| `app/entity_seed/service.py` | 写入 6 台服务器 + 扫描器 IP 的关系边 |
| `app/agent/context_builder.py` | Event 上下文可选附带 `entity_context_snapshot` |
| `app/agent/prompts.py` | 用户 Prompt 增加「优先调用 query_entity_graph 建立关联」 |
| `investigation_sops.recommended_skills` | 种子数据加入 `query_entity_graph` |

#### 2.1.5 CLI / 运维

```bash
# 新命令（建议）
ma-entity-relations-import --file relations.jsonl
docker compose exec app ma-entity-seed   # 扩展后一并写入关系
```

#### 2.1.6 验收标准

- [ ] 对 Event 中 src_ip / host / user 调用 `query_entity_graph` 可返回 ≥1 条关系边（在 seed 环境下）
- [ ] Agent Prompt 表格含 location + 关联摘要
- [ ] 回归用例：有/无实体关系时 verdict 差异可测

---

### EP-02 结构化假设模板 SOP

**目标**：将 `investigation_sops.guidance_text` 升级为可机器校验的假设模板（supporting / refuting hints）。

#### 2.2.1 数据库变更

**迁移**：`013_sop_hypothesis_template.py`

**扩列 `investigation_sops`**

| 字段 | 类型 | 说明 |
|------|------|------|
| `hypothesis_template` | JSONB | 结构化模板，见下 Schema |
| `termination_policy` | JSONB | 外置终止策略（可与 EP-03 共用） |

**`hypothesis_template` Schema 示例**

```json
{
  "version": 1,
  "default_hypotheses": [
    {"id": "h_attack", "label": "真实攻击", "priority": 1},
    {"id": "h_fp", "label": "误报/业务行为", "priority": 2}
  ],
  "supporting_hints": [
    {"id": "s_ti_malicious", "description": "威胁情报标记恶意", "weight": 0.3, "skill": "query_threat_intel"},
    {"id": "s_multi_alert", "description": "同实体多告警", "weight": 0.2, "skill": "query_history_alerts"}
  ],
  "refuting_hints": [
    {"id": "r_scanner", "description": "已知扫描器/值班知识", "weight": 0.25, "skill": "query_asset"},
    {"id": "r_business_hours", "description": "业务时段正常访问模式", "weight": 0.15}
  ],
  "required_skills_before_conclude": ["query_asset", "query_threat_intel"],
  "investigation_intent": "先假设攻击成立，再主动寻找反证；若反证充分则倾向误报。"
}
```

#### 2.2.2 Skill

| Skill | 改动 |
|-------|------|
| 无新 Skill | — |
| `submit_conclusion`（`app/agent/conclusion.py` + tool 定义） | 增加可选字段 `hypotheses_evaluated[]`、`refutation_summary` |

#### 2.2.3 配置项

| Key | 默认 | 说明 |
|-----|------|------|
| `investigation.hypothesis_template_enabled` | `true` | 是否注入结构化 SOP |
| `investigation.require_refutation_attempt` | `true` | 裁决为 attack_confirmed 前必须记录反证尝试 |
| `investigation.min_refuting_hints_checked` | `1` | 至少评估 1 条 refuting hint |

#### 2.2.4 代码触点

| 模块 | 改动 |
|------|------|
| `app/agent/prompts.py` | `build_system_prompt` 渲染 hypothesis_template |
| `app/agent/context_builder.py` | 加载 SOP 时带上 template |
| `alembic/versions/005_investigation_seed.py` 或新 seed | 为 `brute_force` 等类别写入 template |
| `web/src/pages/SettingsPage.tsx` | （P1）SOP 模板只读预览 |

#### 2.2.5 验收标准

- [ ] Prompt 中包含 supporting/refuting hints 列表
- [ ] 结论 JSON 含 `hypotheses_evaluated`
- [ ] 未调用 `query_threat_intel` 时，`attack_confirmed` 可被外置规则拒绝（见 EP-03）

---

### EP-03 外置终止与证据闭合度

**目标**：调查结束不由 Agent「主观查够了」，而由**证据闭合度 + 必填 Skill + 反证覆盖**外置判定。

#### 2.3.1 数据库变更

**迁移**：`014_investigation_closure_metrics.py`

**扩列 `investigation_conclusions`**

| 字段 | 类型 | 说明 |
|------|------|------|
| `evidence_closure_score` | float | 0–1，规则引擎计算 |
| `refutation_coverage` | float | 0–1，refuting hints 覆盖比例 |
| `hypotheses_evaluated` | JSONB | Agent 提交的假设评估 |
| `closure_checks` | JSONB | 每项校验 pass/fail 明细 |
| `closure_passed` | boolean | 是否通过外置终止门槛 |

**扩列 `investigations`**

| 字段 | 类型 | 说明 |
|------|------|------|
| `closure_requested_at` | timestamptz | Agent 首次请求结束时间 |
| `closure_retry_count` | int | 因未通过校验被驳回次数 |

#### 2.3.2 Skill / 服务

| 组件 | 说明 |
|------|------|
| **`ClosureEvaluator`**（新服务 `app/agent/closure_evaluator.py`） | 纯规则：统计 tool_calls 覆盖的 hint / required_skills |
| **`submit_conclusion` 流程** | 先 `ClosureEvaluator.evaluate()`，不通过则返回 tool error 要求补查 |

**闭合度计算（初版规则）**

```text
score = 0.4 * required_skills_coverage
      + 0.3 * supporting_hints_matched
      + 0.3 * refuting_hints_attempted
通过门槛：score >= investigation.min_evidence_closure_score (默认 0.6)
attack_confirmed 额外要求：refutation_coverage >= 0.5
```

#### 2.3.3 配置项

| Key | 默认 | 说明 |
|-----|------|------|
| `investigation.closure_enabled` | `true` | 启用外置终止校验 |
| `investigation.min_evidence_closure_score` | `0.6` | 最低闭合度 |
| `investigation.min_refutation_coverage_for_attack` | `0.5` | 确认攻击前反证覆盖 |
| `investigation.max_closure_retries` | `2` | 驳回后最多补查轮次 |
| `investigation.allow_conclude_without_ti` | `false` | 公网 IP 是否强制 threat_intel |

#### 2.3.4 代码触点

| 模块 | 改动 |
|------|------|
| `app/agent/loop.py` | 拦截 submit_conclusion |
| `app/agent/orchestrator.py` | 持久化 closure 字段 |
| `app/eval/regression/` | 新增 closure 相关断言 |

#### 2.3.5 验收标准

- [ ] 故意跳过 `query_threat_intel` 时，`attack_confirmed` 被驳回并提示补查
- [ ] `investigation_conclusions.closure_checks` 可在事件详情/轨迹页展示
- [ ] `insufficient_information` 不受 closure 驳回（允许证据不足退出）

---

## 三、P1 工作包详单

### EP-04 调查监督审计

**目标**：轻量「监督者」——不新增独立 Agent，用**规则 + 可选小模型**做事后/提交前审计。

#### 3.1 数据库

**迁移**：`015_investigation_audits.py`

**新建表 `investigation_audits`**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `investigation_id` | UUID FK | |
| `audit_type` | varchar(32) | `pre_submit` / `post_complete` |
| `passed` | boolean | |
| `findings` | JSONB | 如 hallucination_risk、missing_skill、path_drift |
| `supervisor_model` | varchar(64) | `rules` 或 LLM 模型名 |
| `created_at` | timestamptz | |

#### 3.2 服务（非 Skill）

**`InvestigationSupervisor`**（`app/agent/supervisor.py`）

| 检查项 | 规则示例 |
|--------|----------|
| 证据引用 | `evidence_refs` 中 ID 是否存在于 tool_calls 输出 |
| 路径漂移 | 是否调用与 SOP 无关 Skill 超过 N 次 |
| 遗漏点 | required_skills 未调用 |
| 幻觉风险 | reasoning 中出现 tool_output 未出现的 IOC（正则/简单 NER） |

#### 3.3 配置项

| Key | 默认 | 说明 |
|-----|------|------|
| `investigation.supervisor_enabled` | `true` | |
| `investigation.supervisor_mode` | `"rules"` | `rules` / `llm` |
| `investigation.supervisor_block_on_fail` | `false` | true=审计失败改 verdict 为 needs_human_review |
| `investigation.supervisor_llm_model` | null | mode=llm 时使用 |

#### 3.4 Web

- 事件详情 / 调查轨迹页增加「监督审计」折叠面板
- 仪表盘：监督失败率（7 日）

---

### EP-05 初筛智能化与 Token 成本看板

**目标**：对齐 PDF「分诊不必全 Agent；调查要控 Token」。

#### 3.5.1 数据库

无需新表。利用已有：

- `investigations.token_input` / `token_output` / `skill_call_count`
- `triage_results.llm_assist_score`（已有列）

#### 3.5.2 逻辑改动

| 模块 | 改动 |
|------|------|
| `app/triage/handlers/llm_assist.py` | 仅对 `queue_uncertain` 或分数在 uncertain_band 内启用 |
| `app/api/routes/dashboard.py` | 新增 `investigation_cost`：avg_token/event、P95 耗时 |
| `app/agent/orchestrator.py` | 记录 `finished_at - started_at` 至 audit detail |

#### 3.5.3 配置项

| Key | 默认 | 说明 |
|-----|------|------|
| `triage.llm_assist_route_filter` | `["queue_uncertain"]` | 仅这些路由调用 LLM |
| `triage.llm_assist_max_per_run` | `20` | 每轮初筛 LLM 上限 |
| `investigation.metrics_enabled` | `true` | 仪表盘展示成本 |
| `investigation.target_tokens_per_event` | `10000` | 告警阈值（仅展示） |
| `investigation.prompt_compression_enabled` | `false` | P2：告警摘要压缩 |

#### 3.5.4 Web

- 仪表盘卡片：今日调查数 / 平均 Token / 平均耗时
- 设置 → 系统配置说明更新

---

### EP-06 告警关联扩线

**目标**：跨告警拼攻击故事，而非单条 alert 调查。

#### 3.6.1 数据库

**扩列 `events`**

| 字段 | 类型 | 说明 |
|------|------|------|
| `correlation_key` | varchar(128) | 可选，跨 event 关联（如同一 src_ip 24h） |
| `related_event_ids` | UUID[] | 调查时发现的关联 Event |

#### 3.6.2 Skill

**新建 `query_correlated_alerts`**

| 项 | 内容 |
|----|------|
| 入参 | `entity_type`, `entity_key`, `window_hours`, `exclude_event_id` |
| 行为 | 查 `alerts` + `events` + `triage_results`，返回同源/同实体其他 Event 摘要 |
| 与现有关系 | 可合并进 `query_history_alerts` 的 `mode=correlation` 参数，减少 Skill 数量 |

**推荐**：扩展 `query_history_alerts` 而非新建（更省 Token）

```json
// query_history_alerts 新增参数
{ "mode": "same_entity_events", "window_hours": 72 }
```

#### 3.6.3 配置项

| Key | 默认 | 说明 |
|-----|------|------|
| `investigation.correlation_window_hours` | `72` | 关联查询窗口 |
| `investigation.auto_raise_priority_on_correlation` | `true` | 发现关联 Event 时提高 queue_priority |

---

### EP-08 评测与回归扩展

**目标**：把 EP-01~03 变成可自动化回归。

#### 3.8.1 数据（`regression_test_cases` JSONB，无新表）

新增用例标签：

| 标签 | 场景 |
|------|------|
| `entity_graph` | 必须调用 query_entity_graph |
| `refutation` | 误报场景必须尝试反证 |
| `closure_reject` | 应被 closure 驳回后补查 |
| `supervisor_fail` | 监督应标记 hallucination_risk |

#### 3.8.2 配置项

| Key | 默认 | 说明 |
|-----|------|------|
| `eval.require_closure_pass_for_regression` | `true` | 回归是否校验 closure |
| `eval.entity_graph_mock_fixtures` | `{}` | 测试用关系图 fixture |

#### 3.8.3 健康检查

扩展 `health_check_scenarios`：增加 `entity_graph_stage` 探针（注入带关联的 probe payload）

---

## 四、P2 工作包详单

### EP-07 处置推演（只读）

**目标**：对接 PDF「处置推演上下文」——**不自动执行**，仅模拟影响。

#### 4.1 数据库

**迁移**：`016_disposition_simulations.py`

**新建表 `disposition_simulations`**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `investigation_id` | UUID FK | |
| `action_type` | varchar(64) | `block_ip` / `isolate_host` / `disable_user` |
| `action_params` | JSONB | |
| `simulated_impact` | JSONB | 影响主机数、业务中断估计 |
| `approval_status` | varchar(32) | `draft` / `approved` / `rejected` |
| `approved_by_id` | UUID FK users | |
| `created_at` | timestamptz | |

#### 4.2 Skill

**`simulate_disposition`**（只读模拟）

- 调用内部 playbook 或 CMDB 接口（Mock 起步）
- 高敏动作必须 `disposition.require_approval=true` 且 Web 审批

#### 4.3 配置项

| Key | 默认 | 说明 |
|-----|------|------|
| `disposition.simulation_enabled` | `false` | Feature Flag |
| `disposition.require_approval` | `true` | |
| `disposition.allowed_action_types` | `["block_ip"]` | |

---

### EP-09 工具网关（可选）

**目标**：统一 SIEM/EDR/TI/CMDB 对接，Skill 不直接散落 HTTP 调用。

#### 4.4 数据库

**`tool_gateway_credentials`**（加密存密钥引用，非明文）

#### 4.4 架构

```text
Skill → ToolGatewayClient → 适配器(wazuh/cmdb/ti) → 结构化 JSON
```

#### 4.4 配置项

| Key | 默认 | 说明 |
|-----|------|------|
| `tools.gateway_enabled` | `false` | |
| `tools.gateway_timeout_seconds` | `30` | |
| `tools.gateway_audit_all_calls` | `true` | 写入 audit_logs |

---

## 五、迁移顺序建议

| 顺序 | 迁移文件 | 依赖 |
|------|----------|------|
| 1 | `012_entity_relations.py` | — |
| 2 | `013_sop_hypothesis_template.py` | — |
| 3 | `014_investigation_closure_metrics.py` | EP-02 模板 |
| 4 | `015_investigation_audits.py` | EP-03 |
| 5 | `016_disposition_simulations.py` | 可选 |

**配置 seed**：每个迁移附带 `system_config` 新键 + `system_config_descriptions.py` 中文说明。

---

## 六、Skill 全量清单（阶段二后）

| Skill | 状态 | 阶段 | 说明 |
|-------|------|------|------|
| `query_asset` | 已有 | — | 扩展 related_entities |
| `query_history_alerts` | 已有 | EP-06 | 扩展 correlation mode |
| `query_threat_intel` | 已有 | — | — |
| `submit_conclusion` | 已有 | EP-02/03 | 增加假设/闭合字段 |
| `query_entity_graph` | **新建** | EP-01 P0 | 实体关系 BFS |
| `query_correlated_alerts` | 新建或合并 | EP-06 P1 | 建议合并 history |
| `simulate_disposition` | **新建** | EP-07 P2 | 处置推演 |

**`investigation_sops.recommended_skills` 建议值（阶段二）**：

```json
["query_entity_graph", "query_asset", "query_history_alerts", "query_threat_intel"]
```

---

## 七、Web 控制台改动清单

| 页面 | 改动 | 工作包 |
|------|------|--------|
| 仪表盘 `/` | Token/耗时、监督失败率、关联 Event 数 | EP-04/05 |
| 事件详情 | 实体关系图（简版）、closure_checks、监督 findings | EP-01/03/04 |
| 调查轨迹 | 假设模板引用、闭合度评分 | EP-02/03 |
| 设置 | 新 config 键说明；SOP 模板预览（只读） | 全部 |
| 防御资产 | 处置推演审批队列 | EP-07 |
| 评测 | 新回归标签筛选 | EP-08 |

---

## 八、环境变量（阶段二新增/沿用）

| 变量 | 阶段 | 说明 |
|------|------|------|
| `GEOLITE2_CITY_PATH` | 已有 | 归属地，支撑实体上下文 |
| `DEEPSEEK_*` | 已有 | 调查 LLM |
| `ABUSEIPDB_*` / `GREYNOISE_*` | 已有 | 威胁情报 |
| `CMDB_API_URL` | P2 可选 | 实体关系自动同步 |
| `DISPOSITION_MOCK_MODE` | P2 | 推演 Mock |

**原则**：业务阈值进 `system_config`；密钥进 `.env`。

---

## 九、实施排期建议（人天估算）

| 工作包 | 后端 | 前端 | 测试 | 合计 |
|--------|------|------|------|------|
| EP-01 | 3d | 1d | 1d | **5d** |
| EP-02 | 2d | 0.5d | 1d | **3.5d** |
| EP-03 | 3d | 1d | 2d | **6d** |
| EP-04 | 2d | 1d | 1d | **4d** |
| EP-05 | 1.5d | 1d | 0.5d | **3d** |
| EP-06 | 2d | 0.5d | 1d | **3.5d** |
| EP-08 | 1d | 0.5d | 1d | **2.5d** |
| EP-07 | 3d | 2d | 1d | **6d** |
| EP-09 | 5d+ | 1d | 2d | **8d+** |

**MVP（建议先做）**：EP-01 + EP-02 + EP-03 ≈ **2 周**（1 后端 + 0.5 前端）。

---

## 十、风险与约束

1. **不破坏现有约束**：画像 memory 仍不能自动归档；处置仍默认不自动执行。  
2. **closure 过严导致调查卡死**：务必配置 `max_closure_retries` + 最终降级 `needs_human_review`。  
3. **实体关系数据质量**：无 CMDB 时靠 seed/人工导入，需在 UI 标明 confidence。  
4. **Token 成本**：EP-03 驳回补查会增加调用轮次，需与 EP-05 联动监控。  
5. **单 Agent 原则**：阶段二不引入多 Agent Teams，监督用规则服务层实现。

---

## 十一、验收总清单（阶段二 MVP）

- [ ] `entity_relations` 有 seed 数据，`query_entity_graph` 可在调查中调用  
- [ ] 至少 1 个 SOP 含完整 `hypothesis_template`  
- [ ] `attack_confirmed` 缺 threat_intel / 反证时被 closure 驳回  
- [ ] `investigation_conclusions` 持久化 `evidence_closure_score` / `closure_checks`  
- [ ] 仪表盘可见平均 Token / 调查耗时  
- [ ] 回归用例覆盖 entity_graph + refutation 各 ≥1  
- [ ] 运维文档 / 设置页 config 中文说明已更新  

---

## 十二、相关文件索引

| 类型 | 路径 |
|------|------|
| 调查编排 | `app/agent/orchestrator.py` |
| Agent 循环 | `app/agent/loop.py` |
| 结论校验 | `app/agent/conclusion.py` |
| Skill 注册 | `app/skills/bootstrap.py` |
| SOP 模型 | `app/models/investigation.py` → `InvestigationSop` |
| 实体模型 | `app/models/entity.py` |
| 配置说明 | `app/services/system_config_descriptions.py` |
| 配置种子 | `alembic/versions/003~007_*.py` |
| 操作手册 | `docs/MA-MinSight-Operations-Manual.docx` |

---

*本文档随实现进度更新；实现某 EP 时请在对应章节打勾并注明 PR/迁移号。*
