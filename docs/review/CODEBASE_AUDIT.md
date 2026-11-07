# MinSight Codebase Audit

**Version:** 1.2.12  
**Date:** 2026-11-07  
**Spec baseline:** `docs/review/MINSIGHT_PRODUCT_REMEDIATION_SPEC.md` V1.0  
**Companion:** `IMPLEMENTATION_PLAN.md` v1.2.12 · `PRODUCT_OWNER_DECISIONS.md` v1.2.3  
**Mode:** Audit document; **v1.2.12** R-B supplementary — real DB env-vs-system_config **PASS**; remote Actions still **NOT VERIFIED**  

**v1.2.8:** Residual risks R1–R6 planned in `P0_06_RESIDUAL_RISK_CLOSURE_PLAN.md`.  
**v1.2.9:** R-A AUTH-R1 complete on local test DB `ai_sec`; R1 closed; runtime RV still **NOT TESTED**.  
**v1.2.10:** R-B AUTH-R2+R3 — bypass script/CI workflow + `PRIVACY_*` production templates; remote Actions **NOT VERIFIED**; RV still **NOT TESTED**.  
**v1.2.11:** R-B re-verify — `httpx.get/post` gate + mock env adversarial; privacy **36** / full **250/8**.  
**v1.2.12:** R-B supplementary — `test_system_config_env_db_adversarial.py` on `ai_sec`; privacy **41** / full **255/8**; remote Actions blocked (no GitHub remote / gh unauthenticated).  

**Evidence legend:**  
- **Static** = inferred from source review (not executed in this phase)  
- **Unit-tested** = existing pytest asserts the described behavior  
- **Not Found** = no implementation located after search  
- **UNKNOWN** = cannot conclude without runtime / PO input  
- **Proposed** = PO suggestion written in decisions log; not final until confirmed  

---

## 1. Executive Summary

MinSight (`ma-minsight`) has a working Wazuh-oriented pipeline (Ingestion → Triage → Aggregation → Agent → Human Review → Defense Assets), plus Eval, Morning Note, Pilot readonly, JWT/bcrypt, and Docker Compose deployment.

Round-3 doc corrections emphasize: **canonical P0 order identical across all three docs**, **structured (not regex-only) historical HR cleanup**, **Skill/failure classification matrix**, **P0-09 rollback that never restores global auto-suppression**, **MFA upgrade without last-admin lockout**, **Legacy API_KEY 30-day Proposed window**, and **O-02…O-10 marked Proposed**.

| Domain | Maturity | Notes |
|--------|----------|-------|
| Pipeline / Agent | Medium-High | Failure→HR coupling is Critical; matrix required |
| Auth / Pilot | Medium | Pilot core OK; defaults/API key Critical/High |
| Human Review | Medium | Regex detect only — must not auto-cancel on regex alone |
| Defense / Whitelist | Medium | Confirm≠suppress (P0-09); rollback stays suppress-off |
| Audit / i18n / DFD | Low-Medium | Gaps documented |

**Emergency note:** Canonical P0 order starts at P0-03. **O-01 CONFIRMED:** no public instance today → **no** emergency P0-01 queue-jump. Historical contingency remains in D-ORD-02 if future internet exposure occurs.

---

## 2. Current Architecture

### 2.1 Stack

| Layer | Tech | Evidence |
|-------|------|----------|
| API | FastAPI + Uvicorn | `app/main.py`, `pyproject.toml` |
| ORM/DB | SQLAlchemy 2 async, Alembic, PostgreSQL/pgvector | `app/db/`, `docker-compose.yml` |
| Lock/cache | Redis | `app/core/redis.py` |
| Scheduler | In-process APScheduler | `app/scheduler/*` |
| LLM | httpx → DeepSeek-compatible API | `app/llm/client.py` |
| Web | React 18, Vite, Ant Design, TanStack Query | `web/package.json` |

### 2.2 Call graph (summary)

Wazuh → Ingestion → Triage → Aggregation → Investigation(AgentLoop+Skills+LLM) → Human Review → Defense Assets (whitelist/disposition). Schedulers + Redis locks; no Celery (**Not Found**).

### 2.3 Auth mechanisms (summary)

| Mechanism | Path | Privilege |
|-----------|------|-----------|
| JWT Bearer | `deps.require_auth` | User role from DB |
| Env `X-API-Key` | `deps.py` L47–58 | **Full admin** |
| DB `api_keys` table | Model only | **Not wired to auth** (Static) |

---

## 3. Module-by-Module Analysis (with evidence)

### Finding AUD-INV-001 — LLM/ops errors become Human Review

| Field | Content |
|-------|---------|
| **ID** | AUD-INV-001 |
| **Severity** | Critical |
| **Spec** | P0-03, P0-05 |
| **Code paths** | *(Historical static snapshot at audit time.)* LLM/ops error paths previously funneled into security Human Review via `degraded_conclusion` / Event `human_pending`. Orchestrator previously **overwrote** Investigation Status to `NEEDS_HUMAN` when Event routed to `human_pending`. |
| **Trigger path** | Missing/invalid LLM key or HTTP failure during `AgentLoop` step → (pre-remediation) fake security conclusion → Event human_pending → HR dispatch |
| **Current behavior** | **Remediated (P0-03/P0-05):** ops failures → Investigation `FAILED`/`DEGRADED` + `failure_class`; no active security conclusion / no security HR. **Remediated (P0-04):** Event `VERDICT_EVENT_STATUS` is queue routing only and must **not** overwrite Investigation Status (COMPLETED + inconclusive allowed). |
| **Problem** | (Pre-remediation) Violated D-FAIL-* / Spec P0-03; status/verdict conflation |
| **Recommendation** | Keep failure matrix + P0-04 semantic invariants; see `STATUS_VERDICT_SEMANTICS.md` / `P0_04_CLOSURE.md` |
| **Impact** | HR inbox, trust, metrics |
| **Tests** | **Unit-tested (post-remediation):** ops-failure / semantics suites under `tests/agent/` (incl. `test_semantics_p0_04.py`). Historical note: older tests once encoded the bad `degraded_conclusion`→HR path. |
| **Evidence type** | Static (historical) + Unit-tested (post P0-03/05/04) |

---

### Finding AUD-HR-001 — System-error detection without prevention

| Field | Content |
|-------|---------|
| **ID** | AUD-HR-001 |
| **Severity** | High |
| **Spec** | P0-03 |
| **Code paths** | `app/human_review/stale.py` `is_system_error_human_query` L16–22; used in `app/console/queries.py` ~L428 for list flag; `web/src/pages/HumanReviewPage.tsx` L73 regex warning; **not** called from `_pick_dispatch_candidates` / `_dispatch_one` |
| **Current behavior** | Analysts warned but can still answer; reply may reinvestigate (`human_review/service.py` `handle_reply` L178–182) |
| **Problem** | Detection ≠ control; regex alone is **unsafe** for historical auto-cancel (D-FAIL-09) |
| **Recommendation** | Forward path: structured `failure_class` blocks dispatch. Historical cleanup: Investigation ID + structured error type first; ambiguous → admin review queue; retain question/send/cancel_reason; invalidate conclusions (no DELETE). See IMPLEMENTATION_PLAN §5.1 |
| **Tests** | Unit regex only (`test_stale.py`) — **Static** that dispatch ignores helper. **Not Found:** structured cleanup tests (planned T-HR-CLEAN-*) |
| **Evidence type** | Static |

---

### Finding AUD-AUTH-001 — Default admin credentials exposed

| Field | Content |
|-------|---------|
| **ID** | AUD-AUTH-001 |
| **Severity** | Critical |
| **Spec** | P0-01 |
| **Code paths** | `app/core/config.py` L73 `admin_initial_password: str = "changeme"`; L71 weak `jwt_secret` default; L39 weak `api_key` default; `alembic/versions/009_console_seed.py` L36–46 seeds admin with `ADMIN_INITIAL_PASSWORD` or `"changeme"`; `web/src/pages/LoginPage.tsx` L199 `<p className="ms-login-hint">admin / changeme</p>`; i18n placeholders mention changeme (`web/src/i18n/en.ts` / `zh.ts`); `README.md` documents default login |
| **Current behavior** | New installs can use public default; UI advertises it |
| **Problem** | D-AUTH-01..05 violated |
| **Recommendation** | IMPLEMENTATION_PLAN §5 bootstrap |
| **Tests** | **Not Found** test forbidding changeme; `tests/console/test_auth.py` only hash/JWT roundtrip |
| **Evidence type** | Static |

---

### Finding AUD-AUTH-002 — No force change / rate limit / JWT versioning

| Field | Content |
|-------|---------|
| **ID** | AUD-AUTH-002 |
| **Severity** | High |
| **Spec** | P0-01 |
| **Code paths** | `app/api/routes/auth.py` `login` L124–205 (no rate limit); `change_password` L292–313 (no `must_change` gate, no token bump); `create_access_token` `app/services/auth.py` L46–67 payload has `sub/username/is_admin/role/exp` only — **no** `tv`/`jti`; `User` model `app/models/system.py` L17–54 — **Not Found** `must_change_password` / `token_version` columns |
| **Current behavior** | Unlimited login attempts (Static); password change does not invalidate existing JWTs (Static); first-login force change **Not Found** |
| **Recommendation** | Redis rate limit; `must_change_password`; embed `token_version` |
| **Tests** | **Not Found** for rate limit / force change / invalidation |
| **Evidence type** | Static |

---

### Finding AUD-AUTH-004 — Shared env API key = full admin

| Field | Content |
|-------|---------|
| **ID** | AUD-AUTH-004 |
| **Severity** | High |
| **Spec** | P0-02 / D-KEY-* |
| **Code paths** | `app/api/deps.py` `require_auth` L47–58: matching `settings.api_key` → `is_admin=True`, `role=admin`, `is_readonly=False`; ORM `ApiKey` `system.py` L57–76 **Not Found** in verify path (grep: only model + deps env compare) |
| **Current behavior** | Long-lived shared secret with unrestricted write |
| **Problem** | Conflicts with D-KEY-01; automation blast radius |
| **Recommendation** | Scoped DB keys + deprecation window (plan §6); do not hard-cut (D-KEY-02) |
| **Tests** | **Not Found** scoped key tests |
| **Evidence type** | Static |

---

### Finding AUD-SET-001 — System config updates unaudited

| Field | Content |
|-------|---------|
| **ID** | AUD-SET-001 |
| **Severity** | High |
| **Spec** | P0-08 |
| **Code paths** | `app/api/routes/system.py` `update_config` L38–53: load/update/`commit`, **no** `write_audit`; contrast `auth.py` / `users.py` which call `write_audit`; middleware may log `http.put` without before/after body |
| **Problem** | Missing actor-linked before/after config audit |
| **Recommendation** | Explicit audit with redaction |
| **Tests** | **Not Found** config audit test |
| **Evidence type** | Static |

---

### Finding AUD-DEF-002 / P0-09 — Whitelist confirm auto-enables suppression

| Field | Content |
|-------|---------|
| **ID** | AUD-DEF-002 |
| **Severity** | High |
| **Spec** | P0-09 (new), Defense principles |
| **Code paths** | `WhitelistPromoter.confirm_candidate` `app/defense_assets/whitelist/promoter.py` L21–31 increments confirmations; L31 `_promote`; `_promote` L51–58 creates rule `status=WhitelistRuleStatus.ACTIVE` with TTL; `WhitelistHandler.handle` `app/triage/handlers/whitelist.py` L39–51: ACTIVE match → `RouteDecision.ARCHIVE_WHITELIST` short-circuit; UI copy `DefenseAssetsPage.tsx` states “满 3 次后系统自动生成白名单规则” |
| **Trigger path** | Operator confirms candidate N times (default threshold 3 from `DefenseAssetConfig.whitelist_promotion_threshold`) → ACTIVE rule → future alerts archived in triage |
| **Problem** | Knowledge confirm conflated with alert suppression (D-WL-01..03) |
| **Recommendation** | IMPLEMENTATION_PLAN Task P0-09 + §8: separate confirm vs suppression; default off; admin per-rule enable; **rollback must not** restore global auto-suppression or env bypass (D-WL-07) |
| **Tests** | **Unit-tested:** `tests/defense_assets/test_whitelist_promoter.py::test_confirm_third_time_promotes_active` asserts ACTIVE promotion — documents current unsafe coupling |
| **Evidence type** | Static + unit tests |

---

### Finding AUD-DATA-001 — LLM egress of investigation context

| Field | Content |
|-------|---------|
| **ID** | AUD-DATA-001 |
| **Severity** | High |
| **Spec** | P0-06 / D-DATA-* |
| **Code paths** | `LLMClient.chat` `app/llm/client.py` L39–54 POSTs full `messages`+`tools` to `{deepseek_base_url}/chat/completions`; messages built from `build_initial_messages` / prompts including SOP, alert **field table** (src_ip/user/host/url — not wholesale `raw_data` dump in `build_user_prompt`), human replies (`prompts.py`); TI providers GET IP to AbuseIPDB/GreyNoise; WeCom HR markdown; `EmbeddingService.embed` (default disabled) |
| **Current behavior** | External model receives rich alert context when key configured; **Not Found** systematic PII redaction on egress (audit redaction only) |
| **Problem** | Privacy boundary now inventoried but controls incomplete; cannot claim air-gap |
| **Recommendation** | Implement P0-06 remediation sequence in `P0_06_DATA_FLOW_AUDIT.md` §12 after PO authorization |
| **Tests** | **Not Found** egress contract tests |
| **Evidence type** | Static — detailed in `docs/review/P0_06_DATA_FLOW_AUDIT.md` (P0-DATA-01 / P0-DATA-02) |
| **P0-06 Phase 1–3** | Audit + design + **A..E implemented** (`app/privacy/`, report). Residual: runtime RV **NOT TESTED**; P1/P2 batches not started. |

---

### Finding AUD-I18N-001 — Hardcoded Chinese in EN UI

| Field | Content |
|-------|---------|
| **ID** | AUD-I18N-001 |
| **Severity** | High |
| **Spec** | P0-07 |
| **Code paths** | Framework: `web/src/i18n/*`. Hardcoded examples: `DashboardPage.tsx` (multiple zh strings), `DefenseAssetsPage.tsx` L25+, `EventWorkspace.tsx` L13+, `IngestionDiagnosticsPanel.tsx`, `LoginPage.tsx` L199; backend zh errors e.g. `console.py` health/ingestion detail strings |
| **Tests** | **Not Found** i18n CI grep |
| **Evidence type** | Static |

---

### Finding AUD-MFA-001 — Policy gaps vs existing MFA engine

| Field | Content |
|-------|---------|
| **ID** | AUD-MFA-001 |
| **Severity** | High (policy) / Medium (code completeness) |
| **Spec** | P0-01/02, D-MFA-* |
| **Code paths** | Login MFA branch `auth.py` L145–187; verify `mfa_verify` L208–275; pilot create `mfa_required` default **False** `pilot_accounts.py` L76, `CreatePilotRequest` `users.py` L36; admin reset `reset_user_mfa` L103–123 (clears secret, audited); reissue L126–149 (audited). Backup codes **Not Found**. |
| **Current behavior** | Engine works when `mfa_required`; prod admin/pilot defaults not enforced |
| **Recommendation** | Enforce flags; keep reset/reissue; O-05 for backup codes |
| **Tests** | **Not Found** MFA route tests in repo search |
| **Evidence type** | Static |

---

### Finding AUD-AUTH-003 — Session revoke incomplete

| Field | Content |
|-------|---------|
| **ID** | AUD-AUTH-003 |
| **Severity** | Medium |
| **Spec** | P0-01 |
| **Code paths** | `revoke_user` sets `is_active=False` — subsequent `require_auth` L71–72 fails; logout client-only `web/src/api/client.ts`; **Not Found** per-session denylist |
| **Notes** | User revoke works for new requests if is_active checked (yes). Password change without version bump leaves JWT valid until exp (AUD-AUTH-002). |
| **Evidence type** | Static |

---

### Finding AUD-INV-002 — Event lacks non-terminal ops state

| Field | Content |
|-------|---------|
| **ID** | AUD-INV-002 |
| **Severity** | Medium |
| **Spec** | P0-04, D-FAIL-06 |
| **Code paths** | `EventStatus` `enums.py` — no ops_blocked/failed; `InvestigationStatus` FAILED/DEGRADED; O-03 keeps Event at `pending_review` with auto-pick blocked via latest Investigation |
| **PO** | Do not make Event terminal FAILED without business reason — O-03 |
| **P0-04 status** | **Addressed for semantics** — Investigation Status remains independent of Security Verdict; Event queue may still use `VERDICT_EVENT_STATUS` for routing only (not a terminal Event FAILED). See §9a / `STATUS_VERDICT_SEMANTICS.md` / `P0_04_CLOSURE.md`. |
| **Evidence type** | Static + post-implementation unit tests (`tests/agent/test_semantics_p0_04.py`) |

---


### Finding AUD-PIPE-001 / ARCH-001 — Pipeline run history incomplete

| Field | Content |
|-------|---------|
| **ID** | AUD-PIPE-001 |
| **Severity** | Medium |
| **Spec** | P1-05 |
| **Notes** | Locks + coalesce exist; no first-class run table (**Not Found** `pipeline_runs`). Dual triggers: `console.run` admin vs resource `/run` with `require_write`. |
| **Evidence type** | Static |

---

### Finding AUD-DEF-001 — Disposition does not enforce

| Field | Content |
|-------|---------|
| **ID** | AUD-DEF-001 |
| **Severity** | Low (positive) |
| **Code paths** | `DispositionService` `defense_assets/disposition/service.py` L1 (“audit only, no enforcement”), `confirm` L18–32 |
| **Evidence type** | Static; **Not Found** firewall/isolate adapters |

---

## 4. Existing Database Models

Unchanged inventory from v1.0: users, alerts, events, investigations*, human_review*, whitelist_*, disposition_*, entity_*, threat_intel, regression/health, system_config, audit_logs, **api_keys (unused by auth)**.

**Not Found (do not invent yet):** `pipeline_runs`, `evidence_items`, `incidents`, typed `environment_knowledge`, `system_operation_failures` table (prefer Investigation fields first).

---

## 5. Existing APIs

Unchanged high-level map from v1.0. Notable authz:

- Mutations generally `require_write` or `require_admin`.  
- Env API key bypasses to admin.  
- WeCom webhooks: verify separately (review when implementing).  

---

## 6. Security Findings (index)

| ID | Sev | Spec |
|----|-----|------|
| AUD-AUTH-001 | Critical | P0-01 |
| AUD-INV-001 | Critical | P0-03/05 |
| AUD-AUTH-002 | High | P0-01 |
| AUD-AUTH-004 | High | P0-02/KEY |
| AUD-HR-001 | High | P0-03 |
| AUD-SET-001 | High | P0-08 |
| AUD-DEF-002 | High | P0-09 |
| AUD-DATA-001 | High | P0-06 |
| AUD-I18N-001 | High | P0-07 |
| AUD-MFA-001 | High/Med | MFA policy |
| AUD-AUTH-003 | Medium | Sessions |

---

## 7. Reliability Findings

| ID | Sev | Notes |
|----|-----|-------|
| AUD-INV-001 | Critical | Fail→HR |
| AUD-HR-001 | High | No dispatch block |
| AUD-PIPE-001 | Medium | History/retry |
| Single-process scheduler | Medium | Scale/restart coupling (Static) |

---

## 8. Investigation Quality Findings

| ID | Sev | Notes |
|----|-----|-------|
| AUD-INV-001 | Critical | Fake needs_human_review |
| Closure/Supervisor | Positive | Present when LLM works (`closure_evaluator.py`, `supervisor.py`) — Static |
| Timeline/Evidence | Medium | Tool calls exist; product UI incomplete |
| Env knowledge | Medium | Partial entity/on_duty/whitelist |

---

## 9. Missing / Partial Capabilities vs Spec

| Spec | Status |
|------|--------|
| P0-01 | Implemented (see plan); residual break-glass / O-05 still Proposed |
| P0-02 | Implemented (scoped keys + Pilot MFA default); O-02 deadline still Proposed |
| P0-03/05 | Implemented (ops vs security failure matrix + conclusion protection) |
| P0-04 | **Completed** — semantic separation + acceptance in `P0_04_CLOSURE.md` / §9a |
| P0-06 | **A..E conditionally accepted**; **R1 closed**; **R3 PASS** (templates + real DB); **R2** local PASS / remote Actions **NOT VERIFIED**; R-C..R-D / F..N **not** started; runtime/E2E **NOT TESTED** |
| P0-07 | Partial framework |
| P0-08 | Implemented (config/security audit); full-suite residual test debt remains |
| **P0-09** | **High gap** — confirm couples to suppress; rollback policy strengthened in plan §8 |
| P1-01..08 | Partial / Missing as before; Timeline before Briefing |

### 9a. P0-04 semantic separation (implementation evidence)

Independent dimensions (must not be conflated in API/UI/filters):

| Dimension | Meaning |
|-----------|---------|
| Investigation Status | Workflow execution state |
| Security Verdict | Evidence-supported security conclusion |
| Severity | Event / conclusion seriousness |
| Analyst Priority | Urgency of human attention |
| Evidence Strength | Quality and sufficiency of supporting evidence |

Glossary: `docs/review/STATUS_VERDICT_SEMANTICS.md`. Closure: `docs/review/P0_04_CLOSURE.md`.

#### Residual design — `disposition_grade`

`disposition_grade` is derived from **Verdict + Risk** via a **documented response-priority mapping**. It is **not** a second verdict.

Invariants:

- Must **not** modify or overwrite the original Verdict.
- Must **not** be presented as a security verdict.
- Mapping must remain documented and testable.

#### Residual design — Event queue routing (`VERDICT_EVENT_STATUS`)

Example: `INCONCLUSIVE` (`insufficient_information`) → Event `HUMAN_PENDING`.

- This is an **Event queue workflow-routing** mechanism.
- It is **separate** from Investigation Status (Investigation may remain `COMPLETED`).
- It must **not** change the original Security Verdict.
- `HUMAN_PENDING` does **not** mean malicious or confirmed attack.
- New Verdict values must have an **explicitly reviewed** queue-routing policy.

Routing implementation was **not** changed in the P0-04 documentation closure pass.

#### P0-04 test debt (full suite)

Reported full-suite result: **209 passed / 13 failed**. Focused suites: **102 passed**.  
The 13 residuals are **test debt**; baseline overlap with the earlier 8-failure P0-08 baseline is **not independently re-verified** in the docs-only closure (see `P0_04_CLOSURE.md`).

### Skill / failure classification

Ops vs security routing follows the matrix in `IMPLEMENTATION_PLAN.md` §4 (implemented under P0-03/P0-05). Keep regressions covered by agent/HR unit tests.

---

## 10. Recommended Implementation Plan

See `IMPLEMENTATION_PLAN.md` **v1.2.3** and `PRODUCT_OWNER_DECISIONS.md` **v1.2.3**.

### P0 final order (canonical — identical in all three docs)

| # | Task |
|---|------|
| 1 | **P0-03** System Operation Failure separation |
| 2 | **P0-05** Investigation conclusion protection |
| 3 | **P0-01** Default admin account security |
| 4 | **P0-08** Configuration and security audit |
| 5 | **P0-02** Pilot Viewer residual + API key redesign |
| 6 | **P0-04** Status and verdict semantics |
| 7 | **P0-06** Data flow and privacy boundary |
| 8 | **P0-07** Internationalization |
| 9 | **P0-09** Whitelist promotion / suppression safety |

**Emergency override:** not active (**O-01 CONFIRMED**). If future public exposure occurs, follow D-ORD-02 assessment + contingency.

### P1 final order

1. P1-01 Timeline → 2. P1-04 Evidence Ledger → 3. P1-05 Pipeline History → 4. P1-03 Env Knowledge → 5. P1-02 Incident → 6. P1-06 Eval → 7. P1-07 Morning Briefing → 8. P1-08 Dashboard split  

---

## 11. Regression Risks

1. Investigation status/conclusion + failure_class mis-routing  
2. Historical HR cleanup false positives if regex-only (forbidden) / false negatives if admin queue ignored  
3. `token_version` + MFA grace → last-admin lockout  
4. Legacy `X-API-Key` cutover breaking automation  
5. Whitelist suppression off → alert volume spike  
6. i18n missing keys  
7. Enum / filter frontend break  

---

## 12. Questions Requiring PO Decision

See `PRODUCT_OWNER_DECISIONS.md` §B:

| ID | Status |
|----|--------|
| O-01 | **CONFIRMED** (no public deploy) |
| O-02 … O-10 | **Proposed** (written; need final confirm) |

**Still shaping later P0s:** O-02 final deadline, O-03 formal stamp, O-04 whitelist migration, O-05 break-glass, O-07/O-10 matrix.

---

## Data Flow Inventory (P0-06)

**Authoritative Phase 1 audit:** `docs/review/P0_06_DATA_FLOW_AUDIT.md` (executive summary, DFD, full matrix, claim verification, risk register, runtime plan, remediation sequence, open PO questions).  
**Phase 2 implementation design:** `docs/review/P0_06_IMPLEMENTATION_DESIGN.md` (Egress Data Protection Layer, channel policies, config, acceptance, batched tasks).

| Data | Destination | Full / Indicator / Local | Redaction | Configurable / Disable |
|------|-------------|--------------------------|-----------|------------------------|
| Wazuh alerts | Customer Indexer → MinSight DB | Full pull **into** env (`raw_data`) | N/A | Disable data source |
| LLM request | `DEEPSEEK_BASE_URL` (default api.deepseek.com) | **Derived** alert fields + SOP/HR/tool summaries (not wholesale raw JSON in prompt builder) | **EgressGateway** pseudonymize/redact (`app/privacy/`) | Empty key; `privacy.llm_egress_enabled`; BYO URL (still protected) |
| LLM response | Stored in `investigation_messages` / tool calls | Full model output | N/A | same |
| Threat intel | abuseipdb.com / greynoise.io | **Indicator** (IP) | Skip private IPs option | Empty provider keys |
| Entity/history | Local DB; may enter LLM prompts | Local until LLM | Indirect | N/A |
| Embedding | `OPENAI_BASE_URL/embeddings` | Text ≤8k if enabled | Off by default | `embedding_enabled` |
| WeCom | Tencent WeCom APIs / webhook | Review markdown (host/user/reasoning) | Truncation only | Don’t configure |
| App/error logs | Process stdout/files | May include exception strings | Audit path only | Operator log shipping **UNKNOWN** |
| Telemetry | — | **Not Found** in app | — | — |

**UNKNOWN / NOT VERIFIED:** outbound log/metrics agents on host; ECS security-group egress per deploy; runtime DNS capture (see audit §11).

**Supported today (Static):** customer-owned OpenAI-compatible endpoint via `deepseek_base_url` (BYO); disabling external TI/embedding/WeCom by omitting keys/flags; investigation LLM effectively disabled only by empty `DEEPSEEK_API_KEY`. **Note:** `.env.example` omits `DEEPSEEK_BASE_URL` (INFO-DATA-10). Docker network name `internal` ≠ Compose egress isolation.

**P0-06-A..E remediation status:** EgressGateway + HMAC pseudonymization **implemented** (static + unit/contract). Phase 1 findings P0-DATA-01/02 addressed at application layer; **runtime network verification still NOT TESTED**. Full register in `P0_06_DATA_FLOW_AUDIT.md`; acceptance evidence in `P0_06_AE_IMPLEMENTATION_REPORT.md`. **R-B:** CI egress bypass gate + production `PRIVACY_*` templates (`docs/deploy/privacy-config.md`); see residual plan §R2/R3.

---

## Top 10 issues (revised)

1. AUD-INV-001 — Ops failure → Human Review  
2. AUD-AUTH-001 — Default changeme / weak secrets  
3. AUD-HR-001 — Detect but still dispatch (cleanup must not be regex-only)  
4. AUD-AUTH-002 — Rate limit / force change / JWT invalidate  
5. AUD-DEF-002 — Whitelist auto-suppress (P0-09)  
6. AUD-AUTH-004 — Shared admin API key  
7. AUD-SET-001 — Config unaudited  
8. AUD-DATA-001 — Undisclosed LLM egress  
9. AUD-I18N-001 — EN/zh mix  
10. AUD-MFA-001 — Admin/Pilot MFA policy not enforced  

---

## Consistency with plan / decisions (v1.2)

| Check | Result |
|-------|--------|
| P0 order matches IMPLEMENTATION_PLAN §1 and D-ORD-01 | Yes |
| P1 order matches | Yes |
| P0 tasks have tests + acceptance in plan | Yes (plan §5 + matrix T-FAIL / T-HR-CLEAN) |
| DB changes have upgrade + rollback in plan | Yes |
| P0-09 rollback forbids global auto-suppress | Yes (plan §8, D-WL-07) |

---

## Stop

Audit **v1.2** complete. **No code, database, or config modifications.** Awaiting Product Owner **final** approval before any P0 implementation.
