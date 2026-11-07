# P0-06 Phase 2 — 实施设计与隐私决策草案

**版本:** 1.0.0  
**日期:** 2026-11-06  
**状态:** 设计完成；**P0-06-A..E 已按授权实施**（见 `P0_06_AE_IMPLEMENTATION_REPORT.md`）；P1/P2 批次仍待单独授权  
**依据:** `P0_06_DATA_FLOW_AUDIT.md` v1.0.1 · `CODEBASE_AUDIT.md` · `PRODUCT_OWNER_DECISIONS.md`（D-DATA-01..03；O-08/O-09 仍为 Proposed）  
**约束:** 本阶段仅设计与文档；不修改应用代码、测试、迁移、Docker 或配置。

**证据图例:** Static（本阶段源码复核）| Not Found | UNKNOWN（需运行时）| NOT VERIFIED

---

## 0. 文档目的与范围

本文件将 Phase 1 审计结论转化为可执行的 P0-06 实施设计，包括：

1. 对 P0-DATA-01 / P0-DATA-02 的**独立复核**（非照抄审计摘要）。
2. **统一外发数据保护层（Egress Data Protection Layer）**架构。
3. 各外发通道（LLM / TI / WeCom / Embedding / 其他）策略。
4. 客户可配置、**后端强制**的隐私策略模型。
5. 待产品负责人确认的决策（含推荐方案，**不**自动 Confirmed）。
6. 验收标准与分批实施顺序（P0/P1/P2 **任务包**，不改变全局 P0 顺序）。

**明确不做：** 不标记 P0-06 实施完成；不启动 P0-07 / P0-09 / P1。

---

## 1. Phase 1 关键发现独立复核

### 1.1 P0-DATA-01 — Investigation context → LLM 无 PII 脱敏

#### 完整调用链（Static，2026-11-06 复核）

```
InvestigationOrchestrator / AgentLoop.run
  → build_initial_messages(ctx)          # app/agent/prompts.py L114–118
      → build_system_prompt(ctx)         # L10–56：SOP、reference_cases、HR 回复原文
      → build_user_prompt(ctx)           # L83–111：告警字段表含 src_ip/user/host/url
  → 本地持久化 system/user 原文          # app/agent/loop.py L69–72（investigation_messages）
  → 循环：LLMClient.chat(messages, tools) # loop.py L77–81
      → httpx POST {deepseek_base_url}/chat/completions  # app/llm/client.py L39–54
  → 工具结果仅将 SkillResult.summary 追加到 messages     # loop.py L291–294
  → 后续步骤再次将完整 messages（含摘要中的标识符）发往 LLM
```

**并行旁路（同一 LLMClient，同样无外发脱敏）：**

| 入口 | 路径 | 发送内容 |
|------|------|----------|
| Triage LLM assist | `LlmAssistHandler._score_alert` `llm_assist.py` L83–99 → `LLMClient.complete` L88–90 | JSON：`rule_*`, `severity`, `category`, **`src_ip`**, **`host_name`**, **`user_name`** |
| Eval regression | `eval/regression/runner.py` 使用 `LLMClient()` | 评测用例相关 prompt（具体字段依用例；外发同样无保护层） |

#### 实际发送字段（Investigation）

| 来源 | 字段 / 内容 | 是否整份 `raw_data` |
|------|-------------|---------------------|
| Event 摘要 | `event_id`, `title`, `primary_category`, `queue_priority`, `risk_score`, `alert_count`, 时间窗, **`aggregate_host_name`**, **`aggregate_user_name`** | 否 |
| Alert 表行 | `occurred_at`, `rule_name`/`rule_id`, `severity`, **`src_ip`**, `src_geo`, **`user_name`**, **`host_name`**, **`request_url`**, triage 分数/路由 | 否（**派生字段**，非 wholesale JSON） |
| System | SOP `guidance_text`、假设模板、推荐 Skill | 否 |
| Reference | `reference_cases` 整段 JSON（可含特征摘要/推理摘录） | 否 |
| HR | `human_query` + `parsed_content`/`raw_content` 原文 | 否 |
| Tools | `tools` schema + 每轮 `tool` role 的 **summary 文本**（可含 IOC/主机/用户） | 否 |
| Headers | `Authorization: Bearer {deepseek_api_key}` | 密钥仅作认证头，不在 JSON body |

**结论复核：** Phase 1「未把完整 `raw_data` 塞进 prompt builder」**成立**；同时「丰富调查上下文（含 IP/用户/主机/URL/SOP/HR）在无脱敏下外发」**成立**。二者不矛盾。

#### 最终外部接收方

- 默认：`settings.deepseek_base_url` = `https://api.deepseek.com`（`app/core/config.py` L48）+ 路径 `/chat/completions`。
- 可配置为客户自有 OpenAI-compatible 端点（代码能力 VERIFIED；`.env.example` 缺 `DEEPSEEK_BASE_URL` → 披露 PARTIAL）。
- 接收方是否再存储/训练：**UNKNOWN**（提供商政策，超出 MinSight 控制）。

#### 绕过保护层的路径

当前 **不存在** 外发 PII 保护层可供绕过。唯一相近能力是 `redact_for_audit`（见 §1.2），**不被** LLM / WeCom / TI / embed 调用。

因此「绕过」在现状下应表述为：**所有 LLM 外发路径均未经过任何 egress redaction**。

| 路径 | 是否经 `audit_redact` | 是否经拟议 Egress 层 |
|------|----------------------|----------------------|
| `AgentLoop` → `LLMClient.chat` | 否 | 否（Not Found） |
| `LlmAssistHandler` → `complete` | 否 | 否 |
| Eval → `LLMClient` | 否 | 否 |

#### 异常情况是否发送未处理数据

| 场景 | 行为 | 评估 |
|------|------|------|
| `DEEPSEEK_API_KEY` 为空 | `chat` 在发 HTTP 前 `raise RuntimeError`（`client.py` L36–37） | **不外发** |
| HTTP 4xx/5xx / 超时 | `raise_for_status` → AgentLoop 捕获 → ops `FAILED`（P0-03） | 请求可能已到达对端（取决于失败阶段）；**body 仍为未脱敏原文** |
| 部分 Skill 失败 | 继续调查；错误摘要进入 messages 再发给 LLM | 可能含内部错误串；**仍无脱敏** |
| httpx 默认 TLS | 未显式 `verify=False` | 默认校验证书（Static）；自定义私有 CA 行为需部署侧 NOT VERIFIED |

#### 代码锚点

| 组件 | 文件 | 行号（复核） |
|------|------|--------------|
| Prompt 组装 | `app/agent/prompts.py` | L10–56, L83–111, L114–118 |
| 循环调用 | `app/agent/loop.py` | L57, L69–72, L77–81, L291–294 |
| HTTP 外发 | `app/llm/client.py` | L36–54 |
| Triage 旁路 | `app/triage/handlers/llm_assist.py` | L83–99 |
| 默认 URL | `app/core/config.py` | L46–48 |

**复核裁定：** P0-DATA-01 **确认有效**（证据加细，结论与 Phase 1 一致）。

---

### 1.2 P0-DATA-02 — 无集中式 egress redaction

#### 现有「脱敏」范围（Static）

| 模块 | 用途 | 调用方 |
|------|------|--------|
| `app/services/audit_redact.py` `redact_for_audit` | 审计/流水线审计 payload 中密钥类字段 | `app/services/audit.py` L109–113；`pipeline_audit.py` L120–122 |

`_SENSITIVE_KEY_FRAGMENTS` 覆盖 password/token/api_key/mfa 等（`audit_redact.py` L11–35），**不覆盖** `src_ip` / `user_name` / `host_name` / `request_url`，且**从不**应用于 LLM body。

#### 旁路清单（无集中层 → 全部直连 httpx）

| # | 通道 | 发起模块 | 证据 |
|---|------|----------|------|
| 1 | LLM | `LLMClient.chat` | `client.py` L48–54 |
| 2 | Embed | `EmbeddingService.embed` | `embedding.py` L33–34 |
| 3 | AbuseIPDB | `AbuseIPDBProvider.lookup_ip` | `abuseipdb.py` L21–25 |
| 4 | GreyNoise | `GreyNoiseProvider.lookup_ip` | `greynoise.py` L19+ |
| 5 | WeCom corp / webhook | `WeComAdapter` | `adapter.py` L53–65, L82–83 |
| 6 | Eval webhook | `notify_eval_failure` | `notifications.py` L25–26 |
| 7 | Wazuh Indexer | `WazuhIndexerClient` | 入站拉取（客户侧）；非第三方法模型，但同为 httpx 直连 |

#### 异常路径

- LLM/Embed/WeCom：`logger.exception(...)` — **Not Found** 对完整 request body 的 info 级落盘；但仍可能把异常消息（偶含标识符）写入日志。**无**「失败则改发脱敏副本」逻辑；失败即中止或跳过，**成功路径才是主要泄露面**。
- TI：`logger.warning` / `exception` 含 IP（`sync_service.py` ~L90–97）。

**复核裁定：** P0-DATA-02 **确认有效**。集中保护层 **Not Found**；审计脱敏与外发脱敏不可混为一谈。

---

## 2. 统一外发数据保护层（Egress Data Protection Layer）

### 2.1 目标

在**任意**第三方或跨信任边界 HTTP 外发前，强制执行：

1. 通道开关与授权检查；
2. 字段分类与策略应用（禁止 / 脱敏 / 伪名化 / 允许）；
3. 策略版本记录与可审计摘要；
4. 保护失败时 **fail-closed**（拒绝发送）。

本地 DB / Redis / 同信任域 Wazuh 拉取：**默认不走**「第三方法出站」策略；可另设 `trust_boundary=customer_infra` 通道（文档区分，避免误伤入站）。

### 2.2 架构位置与调用方式

```
┌─────────────────────────────────────────────────────────┐
│ 业务模块（AgentLoop / TI sync / WeCom / Embed / Webhook） │
└────────────────────────────┬────────────────────────────┘
                             │ 禁止直接 httpx 到外部（约定 + 测试门禁）
                             ▼
┌─────────────────────────────────────────────────────────┐
│ EgressGateway                                            │
│  - require_channel_enabled(channel)                      │
│  - protect(channel, payload, meta) → ProtectedPayload    │
│  - send(channel, method, url, headers, body)             │
│  - record_egress_audit(channel, policy_version, digest)  │
└───────────┬─────────────────────────────┬───────────────┘
            │                             │
            ▼                             ▼
   EgressPolicyEngine              httpx（唯一出站出口）
   FieldClassifier /               （或注入的 Transport）
   Pseudonymizer / Redactor
```

**推荐模块落点（实施时，非本阶段编码）：**

| 组件 | 建议路径 |
|------|----------|
| 网关 | `app/privacy/egress_gateway.py` |
| 策略引擎 | `app/privacy/policy.py` |
| 字段分类与变换 | `app/privacy/transform.py` |
| 伪名化 | `app/privacy/pseudonym.py` |
| 通道适配 | `app/privacy/channels/{llm,ti,wecom,embed,webhook}.py` |
| 配置加载 | `app/privacy/config.py`（读 `system_config` + env，**后端权威**） |

**调用约定：**

- `LLMClient.chat` **必须**在组 payload 后、`httpx.post` 前调用 `EgressGateway.protect("llm", ...)` 或改为仅通过 Gateway 发送。
- WeCom / TI / Embed / Eval webhook 同理。
- `redact_for_audit` **保留**用于审计存储；可复用密钥片段列表，但 **不得**把审计红action当作 egress 的唯一实现。

### 2.3 输入数据结构

```text
EgressRequest:
  channel: "llm" | "ti" | "wecom" | "embed" | "webhook" | "skill_http"
  destination_class: "third_party" | "customer_controlled" | "unknown"
  content_type: "chat_messages" | "json" | "markdown" | "plain_text" | "query_params"
  payload: Any          # messages[] / markdown / {ip} / text
  context:
    investigation_id?: UUID
    event_id?: UUID
    correlation_id?: str
  policy_override?: none  # 禁止调用方随意降级；仅测试注入
```

```text
ProtectedPayload:
  payload: Any          # 变换后
  policy_id: str
  policy_version: int
  transforms_applied: list[str]   # e.g. ["pseudonym:user", "redact:url_query"]
  blocked_fields: list[str]
  content_digest: str             # hash of protected payload（非原文）
  fail_closed_reason?: str
```

### 2.4 敏感字段识别（分类，非「全部删除」）

| 类别 | 代号 | 示例 | 默认外发策略 |
|------|------|------|----------------|
| **永远禁止** | `SECRET_NEVER` | API key、password、JWT、Bearer、MFA secret、webhook secret、`encoding_aes_key`、私钥 | 删除/替换为 `[REDACTED_SECRET]`；若出现在必发位置 → **整请求失败** |
| **默认脱敏/伪名化** | `PII_DEFAULT` | `user_name`, 邮箱, 内网主机名, 内网/私有 IP, URL query/path 中的账号与 token, `full_log` 摘录, 工号 | 通道策略：伪名化或掩码；不得明文默认出站 |
| **分析可用（受控）** | `ANALYTIC_ALLOWED` | `rule_id`/`rule_name`, `severity`, `alert_category`, 公开 IP（TI 场景）, 粗粒度 geo（国家）, `risk_score`, 事件类别 | 允许按通道白名单外发 |
| **需明确授权** | `CONSENT_REQUIRED` | 完整 `request_url`, 完整主机 FQDN, 明文用户名, 原始 HR 长文本, SOP 中可能含内网拓扑的段落, reference case 全文 | 仅当策略显式 `allow_*` 或非严格模式 + 披露后启用 |

**识别手段（设计）：**

1. **结构化字段路径**（优先）：如 `messages[].content` 内表格列、`summary.src_ip`。
2. **键名启发式：** 复用并扩展 `audit_redact` 片段列表至 egress SECRET。
3. **值形态启发式：** IPv4/IPv6、email、JWT-like、`Bearer `、常见 secret 赋值；用于自由文本（markdown / summary）。
4. **不得**仅靠「删除所有 IP/URL/用户/主机」——否则 LLM/TI 可用性崩溃，且与 SOC 分析需求冲突。

### 2.5 字段级脱敏策略（示例）

| 字段类型 | 变换 | 说明 |
|----------|------|------|
| 用户名 | 稳定伪名化 `user_<hmac8>` | 同 `investigation_id`（或策略 salt 周期）内一致，便于模型关联 |
| 主机名 | `host_<hmac8>` 或保留 TLD 模式 `*.internal` | 严格模式不保留具体标签 |
| 私有 IP | `ip_private_<hmac8>` 或 `[PRIVATE_IP]` | TI 通道：默认跳过查询（已有 `threat_intel_skip_private_ips`） |
| 公网 IP | LLM：可伪名化或保留（策略开关）；TI：保留明文（查询必需） | 见 §3.2 |
| URL | 保留 scheme+host 类别或仅 path 模板；strip query | `CONSENT` 才发完整 URL |
| 密钥 | 立即 `[REDACTED_SECRET]` | fail-closed 若位于 Authorization 误入 body |

### 2.6 一致性伪名化

- 密钥：派生自**仅本地**的 `egress_pseudonym_secret`（env / 系统配置，永不外发）。
- 输入：`HMAC-SHA256(secret, f"{scope}|{field_type}|{raw_value}")` → 截断编码。
- `scope` 推荐：`investigation_id`（调查内一致）或 `tenant_day`（跨调查弱一致，需 PO 决定）。
- **禁止**可逆加密外发「密文当伪名」除非另有密钥隔离设计（本 P0 不引入可逆外发）。

本地 `investigation_messages`：**建议存原文**（分析师调查需要），外发用 Protected 副本；避免用伪名写回污染本地真相源（除非 PO 要求「本地也最小化」——见 Q-DATA-04 相关）。

### 2.7 分通道策略概要

见 §3。引擎按 `channel` 加载 `EgressChannelProfile`（白名单、变换强度、destination_class）。

### 2.8 策略配置与版本

| 项 | 设计 |
|----|------|
| 存储 | `system_config` 键前缀 `privacy.*` + 环境变量覆盖敏感开关 |
| 版本 | 单调 `policy_version`；每次变更写 audit（before/after 经 `redact_for_audit`） |
| 优先级 | **后端强制**：`env 强制关闭 > system_config > 代码安全默认`；前端仅展示 |
| 快照 | 每次外发记录 `policy_id` + `policy_version` + `content_digest` |

### 2.9 脱敏结果审计

记录（本地 `audit_logs` 或专用 `egress_audit` 表——实施时再定，**优先复用 audit_logs**）：

- `channel`, `destination_host`（非完整 URL query）, `policy_version`
- `transforms_applied`, `blocked_fields`
- `content_digest`（**禁止**存原文 payload）
- `success` / `fail_closed_reason`
- `actor` = system / investigation_id

### 2.10 Fail-closed

以下情况 **不得发送**：

1. 通道禁用或未配置却尝试外发。
2. 保护层抛错 / 超时 / 策略加载失败。
3. 变换后仍检测到 `SECRET_NEVER` 残留（二次扫描）。
4. 严格隐私模式下目标 URL 不在允许列表（若启用 allowlist）。
5. `CONSENT_REQUIRED` 字段存在但策略未授权。

失败时：向上返回结构化错误；Investigation LLM 路径对齐现有 ops failure（P0-03），**不得**回退为「发送原文」。

### 2.11 防止新接口绕过

| 控制 | 说明 |
|------|------|
| 单一出站门面 | 业务代码禁止直接 `httpx` 到第三方；仅 `EgressGateway` / 经标记的 `customer_infra` 客户端 |
| CI 门禁 | 测试或 lint：`app/` 下除 `privacy/`、`ingestion/adapters/wazuh`、明确允许列表外，禁止新增裸 `httpx.AsyncClient` |
| 契约测试 | 对 LLM/TI/WeCom/Embed/Webhook 注入 fake transport，断言经 protect |
| 代码评审清单 | 新 Skill/第三方适配器必须登记 `channel=skill_http` 并挂策略 |
| 运行时 | 可选：包装 httpx 事件钩子做防御性断言（P2） |

---

## 3. 分通道外发策略

### 3.1 LLM

| 项 | 设计 |
|----|------|
| 保护对象 | `messages[]`（system/user/assistant/tool）、`tools` schema 中描述（通常无 PII）、**不**把 API Key 写入 body |
| Prompt | 对 `build_*` 产物或发送前整包 messages 做结构化+自由文本变换 |
| Tool arguments | 模型生成的 arguments 回灌下一轮前同样保护（防模型把明文用户名再写出） |
| Tool results | 对 `summary` 做与 PII_DEFAULT 相同变换，保持伪名与 system/user 一致 |
| SOP | 默认外发；若含内网拓扑关键词可标记 CONSENT 或管理员「SOP 外发」开关 |
| Human Review | 默认对回复做伪名化；完整原文仅本地；严格模式可仅发送「已回复：是/否」类摘要（需 PO） |
| 历史上下文 | messages 窗口整包保护；禁止为省事跳过早期轮次 |
| BYO endpoint | `destination_class=customer_controlled` 时可降低变换强度（**配置显式**），但仍强制 `SECRET_NEVER` |
| 禁用 | `privacy.llm_egress_enabled=false` 或空 API key → **不调用** chat；调查 → ops FAILED / 明确错误（与现网空 key 行为一致并文档化） |
| Triage assist | 同通道 `llm`；默认保持 `triage.llm_assist_enabled=false` |

**推荐安全默认（可在 PO 确认前作为实现默认草案）：**

- 公有 LLM：用户名/主机伪名化；URL 去 query；私有 IP 伪名化；规则/严重级别/类别明文；公网 IP 可配置（默认伪名化以免与 TI 混淆）。
- 不得删除全部 IP/主机导致模型无法做网络向推理——用**稳定伪名**替代删除。

### 3.2 Threat Intelligence

| 项 | 设计 |
|----|------|
| 查询字段 | 仅 **IOC 值**（主要为公网 IP）；不发送用户名/主机/告警全文 |
| 授权 | 无 key → 不发送（已有）；建议增加 `privacy.ti_egress_enabled`（默认 true 当且仅当 key 存在时仍可被总开关关闭） |
| 私有 IP | 保持 `threat_intel_skip_private_ips=True` |
| 日志 | 禁止打全文 raw_response 到 info；IP 可用截断或 hash；错误经 redact |
| 与 LLM | Skill `query_threat_intel` 只读本地缓存（已核实）→ 返回 summary 再进 LLM 时走 LLM 保护 |
| 独立禁用 | 总开关或移除 key；两者任一关闭即无出站 |

### 3.3 WeCom

| 项 | 设计 |
|----|------|
| 字段白名单 | 默认：事件短码、类别、风险分数、verdict 标签、`human_query`（可截断）、协查标签 `#EVT-xxxx` |
| 主机/用户/IP | 默认 **不**发明文；改为伪名或「（已隐藏）」；若 Q-DATA-03 认定为客户可控且 PO 允许，可在配置中 `wecom.allow_host_user=true` |
| HR 回复 | 入站原文存本地；再次进入 LLM 时走 LLM 策略 |
| 审计 | 外发 markdown 的 digest + 所用字段列表；不存完整明文到第三方审计副本 |
| 禁用 | 未配置 corp/webhook 或 `privacy.wecom_egress_enabled=false` |

### 3.4 Embedding

| 项 | 设计 |
|----|------|
| 本地 vs 外部 | 当前实现仅为外部 OpenAI-compatible（`embedding.py`）；**本地模型 Not Found** → 文档不得声称本地向量 |
| 默认 | `defense_assets.embedding_enabled=false`（保持）；`embed()` 自身也应读总开关（消除「仅调用方检查」缺口） |
| 输入 | 对 `feature_summary` / query 做与 LLM 类似的 PII 变换后再上传 |
| 向量生命周期 | 存 `judgment_cases.embedding`；删除用例应删向量；保留期跟随 Q-DATA-04 / 资产保留策略 |
| 禁用 | flag + 空 key；Gateway 拒绝 embed 通道 |

### 3.5 其他路径

| 路径 | 策略 |
|------|------|
| Eval webhook | `channel=webhook`；仅 title/detail 经保护；默认 URL 空；禁用即不发送 |
| Telemetry | 产品遥测 **Not Found** → 保持无；若未来新增必须挂 Gateway |
| Docker / 基础设施 | 应用层无法单独证明；RV 计划 + 部署文档；Compose 网络名 `internal` ≠ 隔离（审计已述） |
| 未来第三方 Skill | `channel=skill_http`；强制注册策略档案，否则 CI 失败 |
| Wazuh Indexer | `customer_infra`：拉取告警；不应用「第三方 LLM」级伪名化，但 TLS/凭据规范保留 |

---

## 4. 客户可配置策略（后端强制）

### 4.1 配置项草案（`privacy.*`）

| 键 | 类型 | 安全默认（草案） | 说明 |
|----|------|------------------|------|
| `privacy.strict_mode` | bool | `false`（若 Q-DATA-01 要求 air-gap 则默认 true 需 PO） | 严格模式：公有 LLM URL 拒绝、CONSENT 字段全拒、强制伪名 |
| `privacy.llm_egress_enabled` | bool | `true` 当 key 存在时可用；**总开关可关** | 关则不调用 LLM |
| `privacy.ti_egress_enabled` | bool | `true`（仍需 key） | 独立于 LLM |
| `privacy.wecom_egress_enabled` | bool | `true`（仍需配置） | 独立 |
| `privacy.embed_egress_enabled` | bool | `false` | 与 O-09 对齐 |
| `privacy.webhook_egress_enabled` | bool | `true` 若 URL 配置 | Eval 等 |
| `privacy.llm.allow_public_ip_plaintext` | bool | `false` | |
| `privacy.llm.allow_username_plaintext` | bool | `false` | |
| `privacy.llm.allow_hostname_plaintext` | bool | `false` | |
| `privacy.llm.allow_full_url` | bool | `false` | |
| `privacy.wecom.allow_host_user` | bool | `false` | 依赖 Q-DATA-03 |
| `privacy.ti.require_admin_ack` | bool | `false` 直至 Q-DATA-05 | |
| `privacy.pseudonym_scope` | enum | `investigation` | |
| `privacy.allowed_llm_base_urls` | list | 空=不限制（非严格）；严格模式必填 | |
| `privacy.policy_version` | int | 自增 | 只读展示 |

环境变量可强制：`PRIVACY_STRICT_MODE=1`、`PRIVACY_LLM_EGRESS_ENABLED=0` 等，**优先级高于** DB 配置。

### 4.2 边界与优先级

```
env 强制禁用 > strict_mode 约束 > system_config 通道开关 > 通道内字段开关 > 代码默认
```

前端 Settings **只读写经 API 校验的配置**；所有 `EgressGateway` 决策以服务端加载结果为准。

### 4.3 与现有开关关系

| 现有 | 关系 |
|------|------|
| 空 `DEEPSEEK_API_KEY` | 继续阻止；与 `llm_egress_enabled` **与** 关系 |
| `triage.llm_assist_enabled` | 子开关；总 LLM 关则 assist 必关 |
| `defense_assets.embedding_*` | 与 `embed_egress_enabled` **与** |
| WeCom env | 与 `wecom_egress_enabled` **与** |
| TI keys + `skip_private` | 与 `ti_egress_enabled` **与** |

---

## 5. 待产品负责人确认的决策

**规则：** 下列均为 **Open / Proposed**；本设计**不**写入 `PRODUCT_OWNER_DECISIONS.md` 为 Confirmed。

### 5.1 Q-DATA-01 — 是否要求严格 air-gap / 无外部 LLM

| 项 | 内容 |
|----|------|
| 问题 | 生产客户部署前，是否必须支持「无外部 LLM」模式，或披露后的第三方/BYO LLM 即可？ |
| 推荐 | **披露 + 默认可 BYO**；提供 `strict_mode` / `llm_egress_enabled=false`；**不**默认禁止一切模型（符合已 Confirmed 的 D-DATA-01）。若目标客户强监管，将 air-gap 作为**可售卖配置**而非全局唯一模式。 |
| 安全影响 | 允许外部 LLM 则依赖脱敏与合同；强制 air-gap 则调查能力依赖客户自建模型。 |
| 产品/UX | Air-gap 下无 key/开关关闭 → 调查 FAILED（需清晰文案）；分析师需理解「无模型则无自动调查」。 |
| 可先做的安全默认 | 实施脱敏层、总开关、文档披露；**不等待**也可开工的工程项。 |
| 必须等 PO | 是否把 air-gap 列为**生产准入硬门槛**。 |

### 5.2 Q-DATA-02 — 永不离开环境的字段集

| 项 | 内容 |
|----|------|
| 问题 | 哪些字段永远禁止外发（即使用户想打开）？ |
| 推荐 | **硬禁止：** 一切 SECRET；`full_log`；原始 `raw_data` JSON；密码/Cookie/Authorization 头内容。**默认禁止明文、可配置放宽：** 用户名、内网主机、完整 URL、私有 IP。**允许分析：** rule/severity/category/risk。 |
| 安全影响 | 硬禁止面过大 → 功能受损；过小 → 合规风险。 |
| UX | 设置页用「永远禁止 / 默认隐藏 / 可授权」三档展示。 |
| 可先做 | 按推荐三档实现引擎；具体「可授权」清单以 PO 最终表为准做配置默认。 |
| 必须等 PO | 最终「永远禁止」与「可授权」清单签字。 |

### 5.3 Q-DATA-03 — WeCom 信任分类

| 项 | 内容 |
|----|------|
| 问题 | WeCom 算客户可控消息通道，还是外部 SaaS？ |
| 推荐 | 默认按 **external SaaS** 最小化字段；若客户书面确认企微租户在其安全域内，允许 `destination_class=customer_controlled` + 可选主机/用户。 |
| 安全影响 | 分类错误会导致过度发送或过度削弱协查效率。 |
| UX | 协查卡片可能看不到主机名 → 需短码关联回控制台。 |
| 可先做 | 默认最小化白名单。 |
| 必须等 PO | 正式分类与是否允许 `allow_host_user`。 |

### 5.4 Q-DATA-04 — 保留期

| 项 | 内容 |
|----|------|
| 问题 | `alerts.raw_data` 与 `investigation_messages` 保留多久？ |
| 推荐 | 草案：告警原文 180 天；调查消息 365 天；可配置；提供归档/删除任务（P1）。 |
| 安全影响 | 无限保留扩大泄露面；过短影响追责与复盘。 |
| UX | 历史调查可能被清理；需导出能力说明。 |
| 可先做 | 设计 purge job 接口；**默认值等待 PO**。 |
| 必须等 PO | 具体天数与是否允许「仅删外发副本、留本地」。 |

### 5.5 Q-DATA-05 — TI 是否需额外管理员确认

| 项 | 内容 |
|----|------|
| 问题 | 仅有 API key 是否足够，还是要管理员确认「允许把公网 IP 发给 TI 厂商」？ |
| 推荐 | key 仍为技术开关；增加**一次性** admin acknowledgement 旗标（可审计）再允许首次 sync。 |
| 安全影响 | 减少「配了 key 却不知情外发」。 |
| UX | 多一步设置确认。 |
| 可先做 | 保留 skip private + 文档警告。 |
| 必须等 PO | 是否强制 acknowledgement。 |

### 5.6 相关 Proposed（非新造 Confirmed）

| ID | 推荐推进方式 |
|----|----------------|
| **O-08** | 文档 + `.env.example` 增加 `DEEPSEEK_BASE_URL`；支持声明与代码一致 |
| **O-09** | 保持 embedding 默认关闭；启用需披露 |

### 5.7 可采用安全默认 vs 必须等待

| 可采用安全默认（设计批准后即可编码） | 必须等待 PO |
|--------------------------------------|-------------|
| SECRET_NEVER 强制；集中 EgressGateway；fail-closed | Q-DATA-01 是否生产硬门槛 air-gap |
| LLM/WeCom 默认伪名化用户与主机 | Q-DATA-02 最终字段清单签字 |
| TI 仅 IP、skip private、可总开关 | Q-DATA-03 WeCom 分类 |
| Embed 默认关 + 输入脱敏 | Q-DATA-04 保留天数 |
| 契约测试与 httpx 门禁 | Q-DATA-05 TI acknowledgement |
| 客户披露文档 `DATA_FLOW.md` 草稿 | O-08/O-09 正式 Confirmed 文案 |

---

## 6. 验收标准（可执行）

测试必须覆盖**真实调用链**（mock transport / 记录最终 HTTP body），禁止只测纯函数。

| ID | 标准 | 验证方式 |
|----|------|----------|
| AC-01 | 所有第三方外发路径均经 EgressGateway | 契约测试 + httpx 使用白名单扫描 |
| AC-02 | API Key / 密码 / Token 不会出现在 JSON/markdown body | 注入假密钥于 prompt/HR，断言 outbound 无明文 |
| AC-03 | 敏感字段按策略脱敏/伪名化 | Fixture 含 user/host/url/private IP |
| AC-04 | 同 investigation 内伪名稳定 | 两轮 messages 中同一用户映射相同 |
| AC-05 | LLM / TI / WeCom / Embed **分别**验证 | 每通道至少 1 条集成级测试 |
| AC-06 | 禁用集成后无隐蔽外发 | 关开关后 mock transport 调用计数 = 0 |
| AC-07 | 保护层故障 fail-closed | 强制 protect() 抛错 → 无 HTTP |
| AC-08 | 错误日志无原始敏感正文 | 触发失败，断言 log 无明文用户名/密钥 |
| AC-09 | Docker/运行时目的地可验证 | 执行审计 RV-01/06（授权环境、合成数据） |
| AC-10 | 新增外部集成防绕过 | CI 失败于裸 httpx；示例「故意绕过」测试作为负面用例 |

**补充：**

- AC-11：Triage LLM assist 与 AgentLoop 共用保护语义。
- AC-12：`query_threat_intel` 技能路径不直接出站（回归）。
- AC-13：本地 `investigation_messages` 仍可读原文（若采用「本地原文 + 外发伪名」策略）。

---

## 7. 实施顺序建议（P0-06 内部批次）

**不改变**全局顺序：… → P0-04 → **P0-06** → P0-07 → …  
以下为 **P0-06 任务包内** 的 P0/P1/P2 优先级。

### 7.1 P0（生产客户部署前必须）

| 任务 ID | 内容 | 修改范围 | 依赖 | 迁移 | 测试 | 验收 | 回滚 |
|---------|------|----------|------|------|------|------|------|
| P0-06-A | 发布客户向数据流披露（基于审计） | `docs/` 产品披露 | Phase 1 审计 | 无 | 文档评审 | D-DATA-02 | 撤下文档 |
| P0-06-B | 实现 EgressGateway + SECRET_NEVER + fail-closed | `app/privacy/*`；改造 LLM/WeCom/TI/Embed/Webhook 调用点 | 设计批准 | 无（或仅 config 键） | AC-01/02/07 | 无明文密钥出站 | 特征开关关闭 Gateway 时**禁止**回退明文；只能禁用外发 |
| P0-06-C | LLM messages/tool 伪名化默认策略 | `LLMClient` / loop 发送路径 | P0-06-B | 无 | AC-03/04/05/11 | P0-DATA-01 关闭 | 同 B |
| P0-06-D | 通道总开关后端强制 | `privacy.*` + config API | P0-06-B | 可选 system_config 种子 | AC-06 | 禁用无包 | 配置回滚 |
| P0-06-E | 契约测试 + httpx 门禁 | `tests/` + CI | P0-06-B | 无 | AC-10 | 防绕过 | 移除门禁仅临时且需记录 |

### 7.2 P1（重要隐私与配置）

| 任务 ID | 内容 | 依赖 | 迁移 | 备注 |
|---------|------|------|------|------|
| P0-06-F | WeCom 字段白名单 + 审计 digest | B, Q-DATA-03 倾向 | 无 | |
| P0-06-G | TI 总开关 + 日志脱敏 +（可选）admin ack | Q-DATA-05 | 可能新增 ack 旗标 | |
| P0-06-H | Embedding 输入脱敏 + `embed()` 内建开关 | O-09 | 无 | |
| P0-06-I | 保留/清理 job（告警原文与 messages） | Q-DATA-04 | 可能 | |
| P0-06-J | BYO 文档与 `.env.example` `DEEPSEEK_BASE_URL` | O-08 | 无 | INFO-DATA-10 |

### 7.3 P2（增强）

| 任务 ID | 内容 |
|---------|------|
| P0-06-K | `strict_mode` + LLM URL allowlist |
| P0-06-L | 运行时 RV-01..08 自动化/半自动清单纳入发布门禁 |
| P0-06-M | httpx 钩子防御性断言；本地向量模型选项（若产品需要） |
| P0-06-N | 营销/法务声明与 §审计声明矩阵对表 |

### 7.4 回滚总原则

- **禁止**「关闭保护层但继续外发原文」作为回滚手段。
- 回滚 = 禁用对应通道外发，或回退到上一 **policy_version** 且仍 fail-closed。
- 不削弱已完成的 P0-01/02/03/05/08 控制。

---

## 8. 与 Phase 1 审计的关系

| 文档 | 关系 |
|------|------|
| `P0_06_DATA_FLOW_AUDIT.md` | **保留**原始证据与声明矩阵；本设计引用并加细复核，不覆盖审计正文 |
| 本文件 | 实施设计与决策草案；批准前不编码 |
| `IMPLEMENTATION_PLAN.md` | 记录 Phase 2 设计完成、实施未开始 |

审计发现 ID 映射：P0-DATA-01 → P0-06-B/C；P0-DATA-02 → P0-06-B；P1-DATA-03 → F；P1-DATA-04 → G；P1-DATA-05 → I；P2-DATA-06 → K；INFO-DATA-10 → J。

---

## 9. 停止条件

Phase 2 设计完成。  

**下一步：** 产品负责人确认 §5 决策（或书面授权「按推荐安全默认先实施 P0-06-A..E」）。  

**在明确批准前：** 不修改应用代码；不开始 P0-07 / P0-09 / P1；不标记 P0-06 实施完成。
