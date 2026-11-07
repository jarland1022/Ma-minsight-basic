# P0-06 剩余风险关闭计划（只读审计 + 下一阶段准备）

**版本:** 1.2.2  
**日期:** 2026-11-07  
**性质:** **v1.2.2** R-B **补充验证** — R3 真实 DB `system_config` 对抗 **PASS**；R2 远程 GitHub Actions **仍阻塞 / NOT VERIFIED**；**v1.2.1** 正式授权复核；**v1.1.0** R-A 仍有效  
**依据:** `P0_06_AE_IMPLEMENTATION_REPORT.md`（有条件接受）· `P0_06_IMPLEMENTATION_DESIGN.md` · `P0_06_DATA_FLOW_AUDIT.md` · `P0_08_PREEXISTING_FAILURE_BASELINE.md`  
**约束:** R-C..R-D / F..N / P0-07 / P0-09 / P1 **仍未授权**；未执行 RV/E2E；**未**改生产库 / 未重启客户服务。

---

## 1. 执行摘要

P0-06-A..E 代码与自动化契约已有条件接受。剩余风险主要落在：**测试环境 Schema 与迁移不同步**、**CI 防绕过覆盖面与流水线接入**、**生产隐私配置模板不完整**、**若干外发路径缺少专用载荷测试**、**运行时网络验证未做**、**日志泄露仅部分验证**。

本文件将每项风险落到证据、关闭所需证据、前置条件、建议实施顺序与验收标准，供产品负责人单独授权后执行。

**不得**把本计划中的建议动作视为已完成；**不得**将 NOT TESTED 改为 PASS。

---

## 2. 当前 A..E 验收状态（不得改变）

摘自最新验收报告，本轮**不修改**这些结论：

| 层级 | 状态 |
|------|------|
| A..E 代码实施 | **完成** |
| 自动化契约 / 定向测试 | privacy **16 passed**；combined **118 passed** |
| 全量测试（验收重跑） | **225 passed / 13 failed / 0 skipped** |
| 运行时网络验证 RV-01..08 | **NOT TESTED** |
| 浏览器 E2E | **NOT TESTED** |
| P0-06-F..N | **未授权** |

PO 立场：有条件接受 A..E；关闭下列剩余风险需**额外授权**的独立阶段。

---

## 3. R1..R6 逐项证据核对

### R1：数据库 Schema 漂移（`api_keys.scopes`）

#### 核实结果

| 检查项 | 证据 | 证据类型 | 结论 |
|--------|------|----------|------|
| ORM 是否定义 `scopes` | `app/models/system.py` `ApiKey.scopes` → `JSONB, nullable=False, default=list`（约 L77） | 代码 | **PASS**（模型有定义） |
| 迁移是否存在 | `alembic/versions/024_scoped_api_keys_p0_02.py`：若缺表则建表；若缺列则 `op.add_column("scopes", ...)` | 代码 | **PASS**（迁移机制存在） |
| 本机 DB 与 ORM 差异 | 验收时 `test_audit_p0_08` 报错：`UndefinedColumnError: column api_keys.scopes does not exist` | 运行时测试失败日志 | **PARTIAL** — 差异在**测试所用 Postgres** 已证实；未对本轮生产库做 schema dump |
| 其他 Schema 初始化 | Alembic 修订链：`024` → `025_pilot_mfa_default_p0_02`；集成 `conftest` 仅检查 `audit_logs` 列，**不**检查 `api_keys.scopes`（`tests/integration/conftest.py` L49–60） | 代码 | **PASS**（机制存在）+ 预检缺口 **PARTIAL** |
| 5 项失败是否已修复 | 见下方 **R-A 执行记录** | 运行时 | **PASS（R-A 已关闭）** |

#### R-A 执行记录（AUTH-R1，2026-11-06）

| 步骤 | 结果 |
|------|------|
| 目标库 | **仅** `127.0.0.1` / DB=`ai_sec` / user=`ai_sec`（集成测试默认库；**非** compose 默认 `ma_minsight`） |
| 升级前 | alembic=`023_audit_p0_security`；`api_keys` **无** `scopes` |
| 升级 | `scripts/_r1_upgrade_test_db.py` → `023→024→025`；`has_scopes=True` |
| 鉴权对齐 | 升级后原失败变为 O-07「需 JWT admin」（API Key 403）；PO 确认后将集成测改为 `admin_headers` JWT |
| conftest | 增加 `api_keys.scopes` 缺失 → skip；新增 `admin_headers` fixture |
| `test_audit_p0_08` | **6 passed** |
| 全量 pytest（R-A 后） | **230 passed / 8 failed / 0 skipped** — 剩余 8 项与 `P0_08_PREEXISTING_FAILURE_BASELINE.md` nodeid **一致** |
| 生产库 | **未触碰** |
| 辅助 | `alembic.ini` 注释中 UTF-8 破折号改为 ASCII（修复 Windows GBK 读配置失败） |

#### 严重程度（关闭后）

R1 **已关闭**。剩余 8 失败属既有基线卫生项，**不在** R-A 范围。

---

### R2：CI 防绕过能力

#### R-B 执行后验收（AUTH-R2，2026-11-07）

| 检查项 | 证据 | 类型 | 结论 |
|--------|------|------|------|
| 扫描逻辑 | `scripts/check_egress_bypass.py`：`find_violations` + CLI `--root`；allowlist **仅** `privacy/egress_gateway.py`、`ingestion/adapters/wazuh/client.py` | 代码 | **PASS** |
| httpx / requests / aiohttp | PATTERNS：`AsyncClient`/`Client` + **`httpx.get/post/...`** + requests/aiohttp | 代码+测 | **PASS** |
| urllib / http.client | 已加入 `urlopen`/`Request`/… 与 `HTTP(S)Connection` | 代码+反向测 | **PASS**（构造侧；**不**声称覆盖 SDK 内部网络） |
| `privacy/` 整包排除 | **已移除**；仅 gateway 路径 allowlist；`test_reverse_privacy_non_gateway_not_excluded` | 测 | **PASS** |
| 当前树静态扫描 | 本地 `python scripts/check_egress_bypass.py` → **PASS** | 运行 | **PASS** |
| 反向植入失败 | httpx/requests/aiohttp/urllib/http.client → exit 1；手工 `httpx.get` demo → exit 1 | 测+手工 | **PASS** |
| Wazuh 例外 | allowlist 路径 scan 通过 | 测 | **PASS** |
| CI workflow | `.github/workflows/ci.yml`：checkout → install → bypass 脚本 → `pytest tests/privacy` | 代码 | **PASS**（工作流已落地） |
| 远程 GitHub Actions 跑通 | 见下方 **补充验证阻塞记录** | 远程 | **NOT VERIFIED** |
| 本地等价 CI 步骤 | bypass 脚本 + `pytest tests/privacy` | 本地 | **PASS** |

#### R-B 补充验证 — 远程 Actions（2026-11-07）

| 阻塞项 | 事实 | 结论 |
|--------|------|------|
| `git remote` | 仅 `origin` → `https://gitee.com/jarland/minsight.git`（**无** GitHub remote） | 无法向 GitHub 推送工作流 |
| GitHub CLI | `C:\Program Files\GitHub CLI\gh.exe` v2.103.3 已安装 | 工具可用 |
| `gh auth` | **未登录**；`GH_TOKEN` / `GITHUB_TOKEN` 均未设置 | 无法 `gh pr create` / 触发 Actions |
| 授权约束 | 不得 push main/master；不得改 Secrets/权限；无法触发则停止并报告 | **已停止触发尝试** |
| Actions run URL / SHA | **无**（未产生 run） | **不得**标远程 PASS |

#### 严重程度（关闭后）

R2 **本地+工作流文件 PASS**；**远程 GitHub Actions 仍 NOT VERIFIED**（环境阻塞，非 workflow 内容错误）。补证据前置：GitHub remote + `gh auth login`（或 PAT）+ feature 分支 PR/push（非 main）。

---

### R3：Docker / Production Privacy 配置

#### R-B 执行后验收（AUTH-R3，2026-11-07）

| 检查项 | 证据 | 类型 | 结论 |
|--------|------|------|------|
| compose | `env_file: .env`；注释指向 `docs/deploy/privacy-config.md`；**不**在 compose 硬编码开关 | 配置 | **PASS**（依赖 `.env` 为设计） |
| `production.env.example` | 完整 `PRIVACY_*` 块；`EMBED=false`；无真实密钥 | 配置+测 | **PASS** |
| `.env.example` | 与代码默认对齐的完整清单 | 配置+测 | **PASS** |
| 配置说明 | `docs/deploy/privacy-config.md`：默认值 / 影响 / 必须性 / Admin DB 可否改 | 文档 | **PASS** |
| 空 LLM Key | `test_empty_llm_key_raises_before_http` | 测 | **PASS** |
| 伪名密钥缺失 fail-closed | `test_production_default_jwt_yields_no_pseudonym_secret` + `test_missing_pseudonym_secret_fail_closed_send` | 测 | **PASS** |
| env 强制覆盖（mock） | `test_env_force_wins_over_adversarial_system_config` | 测 | **PASS** |
| env 强制覆盖（真实 DB） | `tests/privacy/test_system_config_env_db_adversarial.py` → **5 passed**；库=`ai_sec@127.0.0.1`（非生产） | 测 | **PASS** |
| DB 试图开通道 / 放宽明文 | env 关通道 + strict；DB 写入相反值；最终策略仍跟 env | 测 | **PASS** |
| 伪名密钥 | 仅 env/settings；DB `privacy.*` 无法覆盖 secret | 测+代码 | **PASS** |
| env 未设时 system_config 生效 | DB 关 llm/ti；无 `PRIVACY_*` → 策略为 false | 测 | **PASS** |
| 配置审计 | `write_audit` + `system_config` / `config.update`；测后清理 | 测 | **PASS** |
| 未放宽明文默认 | 模板仍为 `allow_*=false` / embed off | 静态 | **PASS** |
| 客户生产配置 | **未**修改、**未**部署重启 | 约束 | **PASS**（未触碰） |

#### 严重程度（关闭后）

R3 **模板 + fail-closed + 真实 DB env 对抗均已关闭（PASS）**。生产库未触碰。

---

### R4：Gateway 外发路径专用测试

| 路径 | 间接覆盖 | 专用载荷测试 | 静态代码 | 结论 | 建议最小补测（需授权写测试） |
|------|----------|--------------|----------|------|------------------------------|
| GreyNoise | TI 通道 `test_ti_allows_public_ip_*`（AbuseIPDB URL） | **无** `GreyNoiseProvider` 调用测 | `greynoise.py` → protect+send | **PARTIAL** | Mock transport：公网 IP path 出站；私有/伪名 IP 不请求；通道禁用 0 HTTP |
| triage `llm_assist` | 经 `LLMClient.complete` → Gateway | `tests/triage/test_llm_assist.py` **Mock LLM**，不断言出站 body | `llm_assist.py` L83–99 | **PARTIAL**（行为测有；egress 载荷 **NOT VERIFIED**） | 注入 RecordingGateway：summary 含 user/host/ip → 出站无明文 |
| Eval LLM | `LLMClient` | **无** eval 专用 egress 测 | `eval/regression/runner.py` 构造 `LLMClient()` | **PARTIAL** | 可选：runner 单步 mock Gateway 或复用 LLMClient 测即可文档声明「同 LLM 通道」 |
| WeCom Token | — | `test_vendor_credential_gated_and_disabled` | `send_vendor_credential` | **PASS** | 可选：适配器级集成 mock |
| WeCom 消息 | — | `test_wecom_markdown_pseudonymizes_host_user` | adapter protect+send | **PASS** | 可选：corp vs webhook 两条均断言 |
| Embedding | disable 测 | **无**「启用后 input 脱敏」载荷测 | `embedding.py` | **PARTIAL** | embed_enabled + mock：input 含 user → 请求 JSON 伪名 |
| Webhook | disable 测 | **无**启用后 title/detail 保护测 | `eval/notifications.py` | **PARTIAL** | 启用 URL + mock：detail 含密钥/用户 → 出站脱敏 |

#### 严重程度

**P2** — 主路径 LLM/WeCom/通用 TI 已有契约；缺口在**路径特异断言**，属测试完备性而非已知绕过。

---

### R5：运行时网络验证 RV-01..08

**全部当前状态：NOT TESTED。** 本轮**不执行**。以下为执行准备规格。

| ID | 验证目标 | 所需环境 | 步骤（摘要） | 观察指标 | 预期 / PASS | FAIL | 需客户真环境？ | 敏感数据？ |
|----|----------|----------|--------------|----------|-------------|------|----------------|------------|
| RV-01 | 枚举真实出站目的地 | 隔离 compose；合成告警；可选空 key / 有 key 沙箱 | 空闲+调查期间抓 DNS/TCP 或 HTTP 代理 | 目标 host:port 列表 | 仅配置的 LLM/TI/WeCom/embed/webhook/indexer；无未知域名 | 出现未披露目的地 | 否（实验室即可） | 用合成数据则低 |
| RV-02 | LLM 载荷字段与脱敏 | Mitmproxy / 包装 transport；**合成** event | 触发 AgentLoop 或 chat | 请求 JSON messages | 无 SECRET；PII 为伪名；无 wholesale raw_data | 明文用户/密钥/完整 raw | 否 | 禁止真实告警全文 |
| RV-03 | TI 仅公网 IP | 测试 Key 或 mock；RFC5737 / 文档测试网 | sync 公网+私网 IP | 请求 query/path | 仅公网 IP；私网 skip | 私网外发或附带用户名 | 否 | IP 为指标级 |
| RV-04 | 禁用/空 key 无包 | 同上 | 关 `PRIVACY_*` / 空 key 再触发 | 包计数 | 对应通道 0 包 | 仍有出站 | 否 | 无 |
| RV-05 | 错误日志不泄密 | 触发 4xx/超时/EgressDenied | 应用日志 | 无 Bearer/用户/主机明文 | 仅 reason/errcode | 日志含 prompt/密钥 | 否 | 合成 |
| RV-06 | 基础设施出站 | ECS/SG/防火墙文档+实查 | 对照安全组 | 允许列表 | 与披露一致 | 全开 0.0.0.0/0 且无文档 | 客户侧可选 | 无应用数据 |
| RV-07 | 备份范围 | 卷/备份脚本清单 | 列路径 | pgdata 含 raw_data | 纳入数据分类 | 备份外泄未控 | 运维 | 备份含敏感 |
| RV-08 | GeoIP 无云调用 | 断外网或抓包 + 本地 mmdb | 摄入告警 | 无 MaxMind 云 DNS | 仅本地文件 | 外连 geo 服务 | 否 | IP 查询本地 |

**PASS 总条件：** 授权执行记录写入验收附录；每项有原始证据（pcap/代理日志摘要，已脱敏）。  
**未授权前：** 保持 **NOT TESTED**。

---

### R6：日志泄露与异常处理

| 检查项 | 证据 | 类型 | 结论 |
|--------|------|------|------|
| Gateway 审计日志 | `_record_audit` → `logger.info` 仅 channel/dest/decision/digest/transforms/blocked/corr（`egress_gateway.py` ~L526–535）；**不**记录 messages | 代码 + `test_audit_record_has_no_raw_prompt` | **PASS**（审计结构） |
| Gateway 异常 | `EgressDeniedError(reason)`；transport 失败包装；**未见**记录 request body | 静态 | **PASS**（未见原文日志）；注入测日志全文 **NOT VERIFIED** |
| LLM client | **无** `logger.exception` 于 `client.py` | 代码 | **PASS** |
| AgentLoop | `logger.exception("LLM call failed at step %s", step)` — 异常链可能含 URL/短 reason；通常不含 full messages | 静态 | **PARTIAL** |
| TI | `logger.warning/exception`「IP lookup」+ `exc_info`；dry_run **不再**打印 IP 值（L114–118 仅 verdict/source） | 代码 | **PARTIAL** — traceback 内容 **NOT VERIFIED** |
| WeCom | `logger.warning` 含 `result.error`；gettoken 仅 `errcode` | 代码 | **PARTIAL** |
| Embed / Webhook | `logger.warning` denied reason；`logger.exception` 失败 | 代码 | **PARTIAL** |
| HTTP 请求/响应 dump | Gateway **Not Found** 对 response/request body 的 debug dump | 静态 | **PASS**（未发现） |
| 自动化 vs 静态 | 审计无原文：**有测**；进程日志扫描：**无专用测** | 测试 | 日志运行时 **NOT TESTED** |

#### 建议测试方案（不改代码本轮）

1. 故障注入 + 捕获 caplog：断言无 `Bearer `、测试用户名、测试主机。  
2. 对齐 RV-05。  

#### 严重程度

**P2** — 未见系统性 dump payload；残余为 exception 字符串与运维日志策略。

---

## 4. 严重程度汇总

| ID | 严重程度 | 原因摘要 |
|----|----------|----------|
| R1 | **CLOSED** | R-A 已将测试库升至 `025`；`test_audit_p0_08` 6 passed；全量余 8=基线 |
| R2 | — | **R-B 本地+workflow PASS**；远程 Actions **NOT VERIFIED**（无 GitHub remote / 未登录） |
| R3 | — | **R-B 模板/fail-closed/mock + 真实 DB 对抗 PASS** |
| R4 | P2 | 路径特异载荷测不全 |
| R5 | P0-acceptance 缺口（非代码缺陷） | 有条件接受的显式未测项 |
| R6 | P2 | 日志大多安全；缺运行时/caplog 证明 |

---

## 5. 需要补充的测试清单（授权后实施）

| ID | 测试 | 关闭风险 |
|----|------|----------|
| T-R1-01 | 测试库 `alembic upgrade` 后 `test_audit_p0_08` 全绿 | R1 |
| T-R1-02 | （可选）conftest 预检 `api_keys.scopes` | R1 |
| T-R2-01 | bypass 脚本反向失败用例 | R2 |
| T-R2-02 | CI job 跑 bypass + privacy | R2 |
| T-R3-01 | 文档/模板含 PRIVACY 的清单检查（可脚本 diff） | R3 |
| T-R4-01..07 | GreyNoise / llm_assist egress / embed 启用 / webhook 启用 等 | R4 |
| T-R5-01..08 | RV 执行记录 | R5 |
| T-R6-01 | caplog 故障注入无 PII/密钥 | R6 |

---

## 6. 环境与前置条件

| 工作 | 前置 |
|------|------|
| R1 | 可丢弃/可重建的 Postgres；Alembic 可执行；**非生产** |
| R2 | 仓库写权限（测试/workflow）；PO 批准 CI |
| R3 | 批准修改 `production.env.example`（及可选 compose 注释） |
| R4 | 批准新增 `tests/privacy` 或路径测 |
| R5 | 隔离网络实验室；合成数据；抓包工具；**书面授权** |
| R6 | 同 R4/R5 |

---

## 7. 建议实施顺序（需分步授权）

```text
Phase R-A（环境卫生）     R1 测试库迁移验证
        ↓
Phase R-B（工程门禁）     R2 反向测 + CI 接入；R3 生产模板补 PRIVACY_*
        ↓
Phase R-C（测试完备）     R4 路径专用载荷测；R6 caplog
        ↓
Phase R-D（运行时）       R5 RV-01..08（单独高权限授权）
```

**不**改变全局 P0 顺序；**不**自动等于批准 P0-06-F..N 产品功能（WeCom 深度、保留期等）。本计划是 **A..E 有条件接受后的风险关闭**，可与 F..N 分开授权。

---

## 8. 每项任务验收标准

| 阶段 | PASS 标准 |
|------|-----------|
| R-A | 5× `test_audit_p0_08` PASS（或 skip 原因=缺迁移且文档化）；记录 alembic revision |
| R-B | 反向 bypass 测红/绿正确；CI 日志可查；`production.env.example` 含完整 PRIVACY 且默认不放宽 |
| R-C | R4 表中 PARTIAL 项有专用测 PASS；R6 caplog PASS |
| R-D | RV-01..08 每项有脱敏证据附录；无一项可在无证据时称 PASS |

**FAIL：** 任何阶段若发现明文回退路径或生产库被误升级 → 立即停止并上报。

---

## 9. 需要产品负责人额外授权的工作

| 授权包 | 内容 | 是否改应用代码 |
|--------|------|----------------|
| **AUTH-R1** | ~~测试库 alembic upgrade + 集成测~~ | **已执行（R-A）** |
| **AUTH-R2** | 扩展 bypass 脚本、反向测、加 CI workflow | 脚本/测试/CI |
| **AUTH-R3** | 更新 `production.env.example`（及文档对齐） | 配置模板 only |
| **AUTH-R4/R6** | 新增路径专用测与 caplog 测 | 仅测试代码（建议） |
| **AUTH-R5** | 执行 RV-01..08 | 运维操作；通常不改代码 |
| **AUTH-F..N** | 原设计 P1/P2 产品项 | 应用代码 — **不在本计划默认范围** |

未经对应 AUTH-*：**不得**开始实施。

---

## 10. NOT TESTED / NOT VERIFIED 清单（当前）

| 项 | 标记 |
|----|------|
| RV-01..08 全部 | **NOT TESTED** |
| 浏览器 E2E | **NOT TESTED** |
| 远程 GitHub Actions 跑通 bypass job | **NOT VERIFIED**（阻塞：仅 Gitee remote；`gh` 未登录；无 run URL） |
| bypass 反向失败用例 | **PASS**（R-B） |
| 生产库 schema 是否含 scopes | **NOT VERIFIED**（测库 R-A 已升级） |
| llm_assist / GreyNoise / embed·webhook 启用载荷 | **NOT VERIFIED**（专用；属 R4） |
| 进程日志全文无 PII（运行时） | **NOT TESTED**（属 R6） |
| env 覆盖 system_config（真实 DB 行对抗） | **PASS**（`test_system_config_env_db_adversarial.py`，库 `ai_sec`） |
| P0-06-F..N | **未授权 / 未实施** |

---

## 11. 停止

**R-B 补充验证已完成并停止（v1.2.2）。**  

**本轮已做：** 真实 DB `system_config` 对抗 5 测；尝试远程 Actions → **阻塞未触发**（按授权停止）。  

**未做 / 未授权：** R4–R6、F..N、P0-07/09、P1；**未**改 Gateway / 生产库；**未** push main；**无** Actions 绿建 URL。  

**privacy pytest：** **41 passed / 0 failed / 0 skipped**  
**真实 DB 对抗：** **5 passed**（含于上）  
**全量 pytest：** **255 passed / 8 failed / 0 skipped** — 基线 8 不变（`P0_08_PREEXISTING_FAILURE_BASELINE.md`）。  
**远程 GitHub Actions：** **NOT VERIFIED**。

**R-B 最终验收建议：**  
- **R3：建议接受（PASS，含真实 DB）。**  
- **R2：本地门禁建议接受；远程 Actions 项保持开放直至提供 GitHub remote + 登录后补一次绿建证据。**  
- **整体 R-B：有条件关闭**（远程 CI 证据缺口显式保留）。

**下一步：** 产品负责人可 (a) 有条件接受 R-B；(b) 提供 GitHub 鉴权后单开「仅 R2 远程」补证；(c) 授权 R-C/R-D。**不得**在未授权时启动 R4–R6 / F..N / P0-07 / P0-09。
