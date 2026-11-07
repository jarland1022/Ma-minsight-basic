# P0-06-A..E 实施验收报告

**日期:** 2026-11-06  
**授权范围:** P0-06-A → E（设计文档 `P0_06_IMPLEMENTATION_DESIGN.md`）  
**状态:** A..E **代码实施完成**；PO **有条件接受**（本文件含验收证据核对）；运行时网络验证 / 浏览器 E2E **未完成**；P0-06 P1/P2 **未授权未开始**  
**约束确认:** 未将 Q-DATA-01..05 / O-08 / O-09 标为 Confirmed；未放宽明文外发默认。  
**验收核对轮次:** 2026-11-06（文档-only；无应用代码变更）

### 状态分层（不得混淆）

| 层级 | 状态 |
|------|------|
| 1. A..E 代码实施 | **完成** |
| 2. 自动化契约 / 定向测试 | **通过**（privacy 16；privacy+agent+HR+console 118） |
| 3. 运行时网络验证（DNS/抓包） | **未完成 — NOT TESTED** |
| 4. 浏览器 E2E | **未完成 — NOT TESTED** |
| 5. P0-06 后续批次 F..N | **未授权** |

---

## 1. A..E 完成情况

| 任务 | 状态 | 摘要 |
|------|------|------|
| **A** 披露 | **PASS**（文档+API） | `docs/DATA_FLOW.md` + `GET /api/v1/privacy/disclosure` + `policy` |
| **B** EgressGateway | **PASS**（代码路径核对） | 见 §验收-2；运行时外发 **NOT TESTED** |
| **C** LLM 保护与伪名 | **PASS**（单测+代码） | Gateway 保护 messages/tools；HMAC 见 §验收-1 |
| **D** 通道开关 | **PASS**（代码） | env 强制优先于 system_config；专用 env 覆盖测试 **NOT VERIFIED** |
| **E** 契约测试 + CI | **PASS**（有限） | 16 测试 + bypass 脚本；反向植入失败用例 **NOT VERIFIED** |

---

## 2. 主要修改文件与原因

| 路径 | 原因 |
|------|------|
| `app/privacy/`（`egress_gateway`, `config`, `transform`, `pseudonym`, `types`, `disclosure`） | 统一外发保护层 |
| `app/llm/client.py` | LLM 仅经 Gateway 发送 |
| `app/agent/loop.py` | 注入 investigation 作用域 `EgressContext` |
| `app/agent/failure.py` | egress 拒绝归类为 ops `llm_egress_denied` |
| `app/triage/handlers/llm_assist.py` | 经 `LLMClient.complete` → Gateway |
| `app/threat_intel/providers/abuseipdb.py` / `greynoise.py` / `sync_service.py` | TI 经 Gateway；通道禁用阻断 |
| `app/human_review/adapters/wecom/adapter.py` | 消息保护 + `send_vendor_credential` |
| `app/defense_assets/embedding.py` | Embed 经 Gateway（默认通道关闭） |
| `app/eval/notifications.py` | Webhook 经 Gateway |
| `app/api/routes/privacy.py` + `app/main.py` | 披露/策略 API |
| `app/core/config.py` / `.env.example` | `PRIVACY_*` / `DEEPSEEK_BASE_URL` |
| `app/services/system_config_descriptions.py` | 配置中文说明 |
| `docs/DATA_FLOW.md` | 客户向披露 |
| `tests/privacy/*` / `scripts/check_egress_bypass.py` | 契约与防绕过 |
| `docs/review/P0_06_*` / `IMPLEMENTATION_PLAN.md` / `CODEBASE_AUDIT.md` | 进度记录 |

**数据库迁移:** 无（仅 `system_config` 种子键，幂等 `ensure_privacy_config_keys`）。

---

## 3. 数据分类与策略

实现于 `app/privacy/transform.py`：

| 类别 | 默认行为 |
|------|----------|
| `SECRET_NEVER` | `[REDACTED_SECRET]`；残留密钥扫描失败则 deny |
| `PII_DEFAULT` | HMAC 伪名化（用户/主机/IP）；URL 去 query |
| `ANALYTIC_ALLOWED` | 允许（仍 scrub 密钥模式） |
| `CONSENT_REQUIRED` | 默认最小化自由文本；明文需显式开关（默认关） |
| `UNKNOWN` | 消息正文 scrub；其他字段 `[BLOCKED_UNKNOWN]` |

BYO Endpoint **不**绕过保护（`test_byo_endpoint_still_protects`）。

---

## 4. 伪名化、密钥与轮换

| 项 | 实现 |
|----|------|
| 算法 | `HMAC-SHA256(secret, f"v{key_version}\|{scope}\|{field_kind}\|{value}")` → 前缀+12 hex（`pseudonym.py`） |
| 密钥来源 | `PRIVACY_PSEUDONYM_SECRET` 优先；否则由非默认 `jwt_secret` 派生；生产 + 默认 JWT → **None → fail-closed** |
| 作用域 | `{customer_scope_id}\|{investigation_id}`（默认）；跨客户 scope 隔离已测 |
| 轮换 | `privacy.policy_version` / `key_version` 进入 HMAC 材料；轮换后伪名变化（文档说明，非匿名化） |
| 禁止 | 密钥不入 Prompt/审计原文；文档不声称「已匿名」 |

---

## 5. 外发路径迁移清单

| 路径 | Gateway | 备注 |
|------|---------|------|
| AgentLoop → LLM | 是 | |
| triage `llm_assist` | 是 | 经 LLMClient |
| Eval LLM | 是 | 同 LLMClient |
| AbuseIPDB | 是 | |
| GreyNoise | 是 | protect 后 path IP |
| WeCom message / webhook | 是 | |
| WeCom gettoken | 是 | `send_vendor_credential`（凭证不经 PII 变换） |
| Embedding | 是 | 默认 `embed` 通道关 |
| Eval webhook | 是 | |
| Wazuh Indexer | 否（允许） | 客户侧 ingress；CI allowlist |
| 产品遥测 | Not Found | |

---

## 6. 实际请求载荷测试（mock transport）

| 场景 | 结果 |
|------|------|
| LLM 密钥/用户脱敏后出站 | **PASS** |
| 同 investigation 伪名一致 | **PASS** |
| 跨 tenant scope 隔离 | **PASS** |
| Tool arguments/results 保护 | **PASS** |
| BYO URL 仍保护 | **PASS** |
| TI 公网 IP 保留 | **PASS** |
| WeCom markdown 主机/用户伪名 | **PASS** |
| 审计记录无原始用户/主机 | **PASS** |

真实公网抓包：**NOT TESTED**（需 RV-01 授权环境）。

---

## 7. 通道开关测试

| 通道禁用 | HTTP 请求数 | 结果 |
|----------|-------------|------|
| LLM | 0 | **PASS** |
| TI | 0 | **PASS** |
| Embed / Webhook | 0 | **PASS** |
| WeCom vendor credential | 0 | **PASS** |

---

## 8. Fail-closed 测试

| 场景 | 结果 |
|------|------|
| 伪名密钥缺失 | **PASS**（无 HTTP） |
| `protect()` 抛错 | **PASS**（无 HTTP） |
| 通道禁用 | **PASS** |
| 无「回退明文发送」路径 | **PASS**（代码审查 + 测试） |

---

## 9. CI 防绕过

| 项 | 结果 |
|----|------|
| `scripts/check_egress_bypass.py` | **PASS** |
| `tests/privacy/test_ci_bypass_gate.py` | **PASS** |

---

## 10. 测试结果（验收核对重跑，2026-11-06）

| 套件 | 结果 | 证据类型 |
|------|------|----------|
| `tests/privacy` | **16 passed** | 自动化 |
| `tests/privacy` + `agent` + `human_review` + `console` | **118 passed** | 自动化 |
| 全量 `pytest` | **225 passed / 13 failed / 0 skipped** | 自动化 |
| `scripts/check_egress_bypass.py` | **PASS** | 静态扫描 |

### 勘误

实施报告初稿曾写「225 passed / 8 failed / 5 skipped」。验收重跑确认：

- **失败为 13**（含 5 个 `test_audit_p0_08`），不是 8。
- **skipped = 0**。先前「5 skipped」为误判（测试**名称**含 skip 的用例被 collect 关键字匹配，并非 pytest SKIPPED）。

### 13 个失败用例（名称、原因、基线证据）

#### A 组：与 P0-08 基线文档一致的 8 项（`P0_08_PREEXISTING_FAILURE_BASELINE.md`）

| Nodeid | 本轮原因（观察） | 基线证据 |
|--------|------------------|----------|
| `tests/aggregation/test_event_key.py::test_floor_to_window_start_utc_midnight` | aware vs naive 午夜比较失败 | 基线文档 #1 **一致** |
| `tests/core/test_config.py::test_assemble_database_urls_encodes_special_characters` | DSN dialect 期望不匹配（历史为 `postgresql://` vs `postgresql+psycopg2://`） | 基线 #2 **记载**；本轮未单独 `--tb` 复述断言文本 → 细节 **NOT VERIFIED** 于本轮日志，类别对齐基线 |
| `tests/skills/test_query_threat_intel_timezone.py::test_utc_now_matches_postgres_timestamp_expectation` | 两次 `utc_now()` 微秒序断言失败 | 基线 #3 **一致** |
| `tests/test_models.py::test_all_tables_registered` | 左侧多表：`entity_relations`, `investigation_audits`, `disposition_simulations`, `tool_gateway_credentials` | 基线 #4 **一致** |
| `tests/threat_intel/test_ip_utils.py::test_is_public_ip` | `is_public_ip('203.0.113.1')` → False | 基线 #5 **一致** |
| `tests/triage/test_dedup.py::test_dedup_hit_when_representative_exists` | naive/aware `TypeError` @ `dedup.py:51` | 基线 #6 **一致** |
| `tests/triage/test_dedup.py::test_dedup_resets_expired_window` | 同上 | 基线 #7 **一致** |
| `tests/triage/test_frequency_datetime.py::test_frequency_db_fallback_uses_naive_datetime` | `AlertSnapshot` ValidationError（缺 id 等字段） | 基线 #8 **一致** |

**结论：** 上述 8 项与已记录基线 nodeid **匹配**；可描述为「与 P0-08 基线文档一致的失败集」。**不得**据此推断「与 P0-06 无关」之外的因果（无差分 blame 证明）。

#### B 组：集成测试 5 项（本轮失败，非 skip）

| Nodeid | 本轮原因 | 基线 |
|--------|----------|------|
| `tests/integration/test_audit_p0_08.py::test_config_update_persists_before_after_redacted` | DB schema：`api_keys.scopes` 列不存在（ORM 与库不一致） | P0-08 曾在迁移完整环境 **6 passed**；本环境 schema 落后 → **环境债务**，非「已验证预存于 P0-06 前同一失败形态」 |
| `...::test_admin_can_query_audit_success_vs_filter` | 同上 | 同上 |
| `...::test_http_and_business_share_correlation_id` | 同上 | 同上 |
| `...::test_pipeline_manual_run_started_then_success` | 同上 | 同上 |
| `...::test_pipeline_failure_finalizes_failed` | 同上 | 同上 |

同文件另有 **1 passed**（本轮）。`conftest` 在 Postgres 不可用时会 `pytest.skip`；本轮 DB 可达但缺列 → **failed** 而非 skipped。

### Skipped

本轮全量：**0 skipped**。无无「5 个 skipped 测试清单」。

---

## 11. 迁移与回滚

| 项 | 说明 |
|----|------|
| Alembic | **无**（A..E） |
| 配置种子 | `ensure_privacy_config_keys` 仅插入缺失键 |
| 回滚原则 | **禁止**关闭 Gateway 后明文外发；回滚 = 禁用通道或停用集成 |

---

## 12. 未完成 / NOT TESTED

| 项 | 标记 |
|----|------|
| P0-06-F..N（P1/P2） | **未授权** |
| 浏览器 E2E | **NOT TESTED** |
| 运行时 DNS/流量抓包 RV-01..08 | **NOT TESTED**（不得标 PASS） |
| 完整 air-gap 产品模式 | 未做 |
| 数据保留期 purge | 未做（等 Q-DATA-04） |
| WeCom 深度产品改造 | 未做 |
| env 覆盖 system_config 的专用自动化 | **NOT VERIFIED** |
| CI 反向（故意加裸 httpx 应失败） | **NOT VERIFIED** |
| 生产 Docker 默认含完整 `PRIVACY_*` | **NOT VERIFIED**（`production.env.example` 无 PRIVACY 块） |

---

## 13. 仍待产品负责人确认

仍为 Open/Proposed（**未** Confirmed）：Q-DATA-01..05、O-08、O-09。

---

## 14. 验收矩阵（授权要求 × 证据）

| # | 验收项 | 结果 | 证据边界 |
|---|--------|------|----------|
| 1 | 已知外发路径经 Gateway | **PASS**（静态+契约） | 运行时 **NOT TESTED** |
| 2 | SECRET_NEVER 不在 body | **PASS** | mock transport |
| 3 | PII_DEFAULT 策略处理 | **PASS** | mock |
| 4 | 一致性伪名化 | **PASS** | `test_pii_pseudonym_consistent_within_scope` |
| 5 | 跨客户伪名隔离 | **PASS** | scope 字符串隔离；密钥级租户隔离见 §验收-1 |
| 6 | 密钥缺失 fail-closed | **PASS** | `test_missing_pseudonym_secret_fail_closed` |
| 7 | Gateway 故障 fail-closed | **PASS** | `test_gateway_transform_failure_fail_closed` |
| 8 | 通道独立启停 | **PASS** | 多通道 disable 测试 |
| 9 | 禁用后无 HTTP | **PASS** | mock 计数 0 |
| 10 | Tool args/results | **PASS** | `test_tool_arguments_and_results_protected` |
| 11 | 审计/错误不泄密 | **PARTIAL** | 审计记录测 PASS；进程日志全文 **NOT TESTED** |
| 12 | BYO 不绕过 | **PASS** | `test_byo_endpoint_still_protects` |
| 13 | CI 裸网络检测 | **PARTIAL** | 正向 PASS；反向用例 / urllib 等 **NOT VERIFIED** |

---

## 验收-1. HMAC 伪名化核对

| 检查项 | 证据 | 结果 |
|--------|------|------|
| 密钥来源 | `derive_pseudonym_secret`：`PRIVACY_PSEUDONYM_SECRET` / `settings.privacy_pseudonym_secret` 优先；否则 `jwt_secret` 派生；生产+默认 JWT → `None` | **PASS**（代码） |
| 派生方式 | `SHA256("minsight-egress-pseudonym-key\|{secret}")` 或 `...-v1\|{jwt}` / `...-dev\|{jwt}`；伪名 `HMAC-SHA256(secret, f"v{ver}\|scope\|kind\|value")` 截断 12 hex | **PASS** |
| 客户环境隔离 | `scope` 含 `customer_scope_id`（默认 `postgres_db` 或 `PRIVACY_CUSTOMER_SCOPE_ID`）+ investigation；`test_pseudonym_isolated_across_customer_scopes` | **PASS**（scope 隔离） |
| 不同用途隔离 | `field_kind` 进入 HMAC 材料（user/host/ip/email/generic） | **PASS**（代码） |
| 密钥轮换 | `key_version`/`policy_version` 进入材料；轮换后伪名变化 | **PASS**（代码设计）；运行时轮换演练 **NOT VERIFIED** |
| 密钥缺失 fail-closed | `pseudonym_secret is None` → deny / raise；单测覆盖 | **PASS** |
| 一致性测试 | `test_pii_pseudonym_consistent_within_scope` | **PASS** |
| 可逆还原路径 | 无明文逆变换 API；持有 HMAC 密钥理论上可暴力/字典攻击低熵值，**非**可逆解密通道 **Not Found** | **PASS**（无直接还原函数）；穷举风险文档已声明「非匿名」 |

---

## 验收-2. EgressGateway 覆盖清单

| 路径 | 入口 | Gateway 调用 | 最终发送 | 测试 | 结果 |
|------|------|--------------|----------|------|------|
| LLM 主路径 | `AgentLoop.run` → `LLMClient.chat` | `gateway.send` LLM @ `client.py` | Gateway 内 `httpx.AsyncClient.request` | `test_llm_*` / `test_llm_client_uses_gateway` | **PASS** |
| triage llm_assist | `LlmAssistHandler._score_alert` → `complete` → `chat` | 同上 | 同上 | 经 LLMClient；专用 assist 载荷测 **NOT VERIFIED** | **PASS**（间接）/ assist 专用 **NOT VERIFIED** |
| Tool args/results | messages 内 tool_calls / tool content | `transform_messages` 于 protect | 同上 | `test_tool_arguments_and_results_protected` | **PASS** |
| TI AbuseIPDB | `AbuseIPDBProvider.lookup_ip` | `gateway.send` TI | Gateway httpx | `test_ti_allows_public_ip_and_channel_disable` | **PASS** |
| TI GreyNoise | `GreyNoiseProvider.lookup_ip` | `protect` + `send` | Gateway httpx | 通道测覆盖 TI；GreyNoise 专用 **NOT VERIFIED** | **PARTIAL** |
| WeCom 消息 | `_send_via_corp_app` / `_send_via_webhook` | `protect` markdown + `send` | Gateway httpx | `test_wecom_markdown_*` | **PASS** |
| WeCom Token | `_get_access_token` | `send_vendor_credential` | Gateway httpx（凭证不经 PII 变换） | `test_vendor_credential_gated_and_disabled` | **PASS** |
| Embedding | `EmbeddingService.embed` | `gateway.send` EMBED | Gateway httpx | `test_embed_and_webhook_respect_disable` | **PASS** |
| Eval webhook | `notify_eval_failure` | `gateway.send` WEBHOOK | Gateway httpx | 同上 disable | **PASS** |
| Eval LLM | `eval/regression/runner.py` → `LLMClient` | 同 LLM | 同 LLM | 间接 | **PASS**（间接） |
| Wazuh Indexer | `WazuhIndexerClient` | **不经** Gateway（客户侧 ingress） | 模块内 httpx | CI allowlist | **PASS**（有意例外） |
| 其他 urllib/SDK | — | — | — | 扫描未覆盖 urllib | **NOT VERIFIED** |

静态搜索：业务模块中第三方出站构造已迁至 Gateway；`sync_service` 协议类型仍提及 `httpx.AsyncClient` 但循环已不创建共享 client（Static）。

---

## 验收-3. Fail-closed

| 场景 | 代码行为 | 测试 | 结果 |
|------|----------|------|------|
| Gateway protect 抛错 | 转为 `EgressDeniedError`；**无**原始重试 | `test_gateway_transform_failure_fail_closed` | **PASS** |
| 策略加载失败 | `policy_load_failed` raise | 无专用注入测 | **NOT VERIFIED**（测试）/ 代码路径 **PASS** |
| 密钥缺失 | deny / raise；requests=0 | `test_missing_pseudonym_secret_fail_closed` | **PASS** |
| 未知字段 | `[BLOCKED_UNKNOWN]` 或 scrub 正文 | 无单独断言测 | **PARTIAL** |
| 脱敏异常 | `transform_failed` | 经 Boom protect | **PASS** |
| 通道关闭 | raise；无 HTTP | 多测 | **PASS** |
| 外部请求失败 | `transport_failed`；注释明确不 raw retry | 代码审查 | **PASS**（静态）；故障注入 **NOT VERIFIED** |
| 异常回退原始 HTTP | 业务路径 **Not Found** 对 Gateway 失败后再 `httpx` | 全文检索 | **PASS**（未发现回退） |

`send_vendor_credential`：通道关闭则拒绝；成功路径发送**未变换**的 corpsecret（厂商鉴权必需）——属设计例外，非 PII 回退。

---

## 验收-4. 配置强制执行

| 检查项 | 证据 | 结果 |
|--------|------|------|
| 优先级 | `load_privacy_policy`：默认 → system_config → `os.environ PRIVACY_*` → `settings.privacy_*` → `_apply_strict` | **PASS**（代码顺序） |
| env 强制不可被 DB 覆盖 | env 在 system_config **之后**写入 | **PASS**（静态）；自动化对抗测 **NOT VERIFIED** |
| strict_mode | 钳制明文/embed | **PASS**（代码） |
| API 改配置权限 | `PUT /config/{key}` 需 `require_admin`；`write_audit` fail-closed | **PASS** |
| 管理员绕过 env | 无法通过 system_config 覆盖已设置的 `PRIVACY_*` env | **PASS**（静态推理） |
| 配置变更审计 | `config.update` before/after + redact | **PASS**（P0-08 机制）；本环境 audit 集成因 schema 失败 **NOT VERIFIED** 本轮 |
| Docker 默认 | `docker-compose` 无 PRIVACY；`production.env.example` 无 PRIVACY 块；空 LLM key 默认 | **PARTIAL** — 依赖空 key；显式隐私默认 **NOT VERIFIED** |

---

## 验收-5. CI 防绕过

| 检查项 | 证据 | 结果 |
|--------|------|------|
| 扫描范围 | `app/**/*.py` | **PASS** |
| 客户端类型 | `httpx.AsyncClient/Client`、`requests.*`、`aiohttp.ClientSession` | **PASS** |
| 未覆盖 | `urllib`、`http.client`、SDK 内部、已构造 client 的 `.post` 再导出 | **缺口 — PARTIAL** |
| 排除 | `privacy/egress_gateway.py`、整个 `privacy/`、`wazuh/client.py` | 有意；`privacy/` 整包排除若未来误加裸客户端 **可能漏检** |
| 正向测试 | `test_check_egress_bypass_script_passes_on_current_tree` | **PASS** |
| 反向测试 | 故意添加违规应失败 | **NOT VERIFIED** |
| 新增裸出口使 CI 失败 | 依赖流水线调用该脚本；仓库 **无** `.github/workflows` **Not Found** → 本地脚本 PASS，**CI 集成 NOT VERIFIED** |

---

## 15. 剩余风险（有条件接受）

1. 全量 13 失败中 5 项为 DB schema 漂移（`api_keys.scopes`），阻塞本机审计集成回归。  
2. 运行时外发与日志泄露未抓包验证。  
3. CI 门禁未证明接入远程流水线；客户端种类覆盖不全。  
4. Docker/生产 env 模板未强制列出全部 `PRIVACY_*`。  
5. GreyNoise / triage assist 缺少与主路径同等粒度的专用载荷测试。

---

## 16. 停止

P0-06-A..E：**代码实施完成 + 自动化证据已核对**；PO 有条件接受。  
**不**将运行时验证标为 PASS。  
**不**开始 P0-06-F..N、P0-07、P0-09 或任何 P1。等待产品负责人下一步授权。
