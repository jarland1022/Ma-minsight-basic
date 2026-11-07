# MinSight Implementation Plan (Revised)

**Version:** 1.2.12  
**Date:** 2026-11-07  
**Based on:** CODEBASE_AUDIT.md v1.2.12 + PRODUCT_OWNER_DECISIONS.md v1.2.3  
**Status:** P0-06-A..E **conditionally accepted** (unchanged); **R-A + R-B** — R1 closed; R3 **PASS** incl. real DB; R2 local PASS / remote Actions **NOT VERIFIED** (blocked); R-C..R-D **not** started  
**v1.2.8:** Residual risks R1–R6 plan (`P0_06_RESIDUAL_RISK_CLOSURE_PLAN.md`)  
**v1.2.9:** AUTH-R1/R-A — local `ai_sec` → alembic `025`; full suite **230 passed / 8 failed**  
**v1.2.10:** AUTH-R2+R3/R-B — egress bypass CI gate + production `PRIVACY_*` templates  
**v1.2.11:** AUTH-R2+R3 formal re-verify — `httpx.get/post` + mock env adversarial; privacy **36**; full **250/8**  
**v1.2.12:** R-B supplementary — real DB `system_config` adversarial **5 passed**; privacy **41**; full **255/8**; remote Actions still blocked (Gitee-only remote, gh not logged in)  

---

## 0. Principles

1. Keep audit-confirmed working features; do not rebuild.  
2. Extend existing models, services, APIs, RBAC.  
3. No speculative new tables; justify every migration.  
4. Every DB task: upgrade + rollback + data compatibility.  
5. PO suggestions ≠ already implemented; Proposed ≠ Confirmed.  
6. Unresolved architecture → **UNKNOWN** or **Proposed**.  
7. **O-01 CONFIRMED:** no public MinSight instance today → execute normal P0 order (**P0-03 → P0-05 → P0-01**). Do **not** emergency queue-jump P0-01. P0-01 remains mandatory P0 before formal production customer deploy; future public exposure needs a dedicated external-exposure security assessment (D-ORD-02).

---

## 1. Final P0 order (canonical — must match all three docs)

| # | Task ID | Title | Severity |
|---|---------|-------|----------|
| 1 | P0-03 | System Operation Failure separation | Critical |
| 2 | P0-05 | Investigation conclusion protection | Critical |
| 3 | P0-01 | Default admin account security | Critical |
| 4 | P0-08 | Configuration and security audit | High |
| 5 | P0-02 | Pilot Viewer residual + API key redesign | High |
| 6 | P0-04 | Status and verdict semantics | Medium |
| 7 | P0-06 | Data flow and privacy boundary | High |
| 8 | P0-07 | Internationalization | High |
| 9 | P0-09 | Whitelist promotion / suppression safety | High |

**Priority note (O-01 CONFIRMED):** No publicly accessible deployment (local / customer private networks only). **No** emergency P0-01 insert. Keep sequence **1 P0-03 → 2 P0-05 → 3 P0-01**. P0-01 is **not** downgraded and **must** complete before formal production customer deployment. Future internet exposure → dedicated external-exposure security assessment first.

**P0-03 + P0-05** ship as one continuous design/test package.

---

## 2. Final P1 order

| # | Task ID | Title |
|---|---------|-------|
| 1 | P1-01 | Investigation Timeline |
| 2 | P1-04 | Evidence Ledger (shared IDs with Timeline) |
| 3 | P1-05 | Pipeline Run History |
| 4 | P1-03 | Environment Knowledge |
| 5 | P1-02 | Incident Correlation |
| 6 | P1-06 | Eval Quality Dashboard |
| 7 | P1-07 | Morning Briefing |
| 8 | P1-08 | Analyst / Admin Dashboard |

---

## 3. Satisfied — do not rebuild

| Area | Evidence | Action |
|------|----------|--------|
| bcrypt password hashing | `app/services/auth.py` `hash_password` | Keep |
| Pilot role + expire + CIDR + `require_write` | enums, `deps.py`, `pilot_accounts.py` | Harden only |
| Disposition confirm non-enforcement | `DispositionService` | Keep |
| Verdict enum values | `InvestigationVerdict` | Keep names |
| Redis pipeline locks | lock helpers | Reuse |
| TOTP MFA challenge/setup | `auth.py`, `mfa.py` | Enforce policy |
| Admin MFA reset/reissue + audit | `users.py` | Keep as multi-admin recovery |
| Embedding default off | `embedding_enabled=False` | Keep (O-09 Proposed) |
| BYO OpenAI-compatible base URL | `deepseek_base_url`, `openai_base_url` | Document (O-08 Proposed) |
| InvestigationStatus FAILED/DEGRADED | `enums.py` | Reuse for ops failure |

---

## 4. Skill / failure classification matrix (P0-03 / P0-05)

Used by AgentLoop + orchestrator to decide status, Human Review, and verdict eligibility.

| Class | Examples | Investigation outcome | Security Human Review? | Deterministic attack/FP verdict? |
|-------|----------|----------------------|------------------------|----------------------------------|
| **LLM service failure** | Missing `DEEPSEEK_API_KEY`, HTTP 4xx/5xx, timeout to model | `FAILED` (+ structured `error_type=llm_service`) | **No** | **No** |
| **Required Skill failure** | Skill marked required by SOP / closure policy fails hard (auth, timeout after retries) | `FAILED` or `DEGRADED` per policy; record missing evidence | **No** (ops) | **No** |
| **Optional Skill failure** | Non-required skill timeout/error | Investigation **may continue**; mark missing evidence / degraded evidence strength | **No** solely for this | Only if remaining evidence supports; else insufficient / no attack/FP |
| **Data source failure** | Wazuh/query backend unavailable for a required lookup | Treat like required skill/datasource ops failure → `FAILED`/`DEGRADED` | **No** | **No** |
| **Security evidence insufficient** | Skills ran; closure fails; analyst questions remain | `NEEDS_HUMAN` + real security conclusion (`insufficient_information` / `needs_human_review`) | **Yes** | **No** deterministic attack/FP without support |
| **Business context insufficient** | Need human env knowledge (scanner? maintenance?) | Same as security evidence gap → HR with real `human_query` | **Yes** | **No** |

**Rules:**

1. System / LLM / required-skill / datasource failures **must not** create Security Human Review.  
2. Optional skill failure ≠ unconditional Investigation `FAILED`.  
3. Incomplete investigations **must not** emit unsupported `attack_confirmed` / `likely_false_positive`.  
4. Structured `error_type` / `failure_class` stored on Investigation (JSON or columns) — not only free-text `human_query`.

### Matrix test scenarios (required)

| ID | Scenario | Expect |
|----|----------|--------|
| T-FAIL-01 | Empty LLM API key | Inv FAILED; no HR request; no security conclusion; Event not human_pending |
| T-FAIL-02 | LLM HTTP 500 mid-loop | Same as T-FAIL-01 |
| T-FAIL-03 | Required skill hard-fail after retries | FAILED/DEGRADED ops; no HR; missing skill recorded |
| T-FAIL-04 | Optional skill timeout; required path OK | Continues; missing_evidence flagged; may conclude insufficient or valid verdict if supported |
| T-FAIL-05 | Datasource down for required asset lookup | Ops failure path; no HR |
| T-FAIL-06 | Skills OK but closure insufficient | Security HR allowed; verdict insufficient/needs_human_review |
| T-FAIL-07 | Business context question only | Security HR with proper human_query |
| T-FAIL-08 | Single optional skill timeout | **Not** blanket FAILED for all investigations |
| T-FAIL-09 | Re-run after fix | New Investigation id; old FAILED row unchanged; no duplicate HR from old row |
| T-FAIL-10 | Unsupported attack_confirmed when skills failed required path | Rejected / not persisted |

---

## 5. P0 Tasks

### Task P0-03 — System Operation Failure separation

| Field | Content |
|-------|---------|
| **Task ID** | P0-03 |
| **Severity** | Critical |
| **Current implementation** | LLM/ops errors → `degraded_conclusion` → `needs_human_review` → Event `human_pending` → HR dispatch. Regex-only system-error detection for UI. |
| **Code paths** | `llm/client.py` L36–37; `agent/loop.py` L73–76; `conclusion.degraded_conclusion` L56–65; `orchestrator.py` L40–45, L262–266, L268; `human_review/service.py` L249–311; `stale.is_system_error_human_query` L16–22 |
| **Required changes** | Apply failure matrix (§4). Persist structured `failure_class` / `error_type` on Investigation; set `error_message`; status FAILED/DEGRADED. Skip fake security conclusion for ops classes. Event: **Proposed O-03** — remain `pending_review`, **block auto re-pick** until explicit admin re-run (**§9.1**). No HR create for ops. |
| **Historical HR cleanup (strengthened)** | See §5.1 below — **not** regex-only cancel. |
| **DB impact** | Additive: Investigation `failure_class` / `error_code` (or JSON `failure_detail`); Conclusion `invalidated_as_ops_failure` bool + `invalidated_at` / `invalidated_reason` (or reuse `is_overridden` with structured detail). HR: ensure cancel reason stored (extend status detail JSON or column `cancel_reason`). **No physical deletes.** |
| **API impact** | Ops failure queue; explicit re-run; admin review queue for ambiguous historical HR |
| **Migration strategy** | §5.1 migration; additive columns nullable; backfill structured marks where Investigation linkage proves ops fault |
| **Regression risks** | Legitimate HR cancelled; events never re-picked; optional skill over-failed |
| **Test cases** | T-FAIL-01..10; T-HR-CLEAN-* (§5.1); T-PICK-* (§9.1) |
| **Acceptance criteria** | Spec P0-03 + D-FAIL-* ; no ops→HR; Event not terminal FAILED; §9.1 auto-pick rules |
| **Rollback** | Feature flag to pause new routing; **do not** mass-uncancel HR; columns remain |

#### 5.1 Historical Human Review cleanup rules

**Forbidden:** Cancelling SENT/open HR **solely** because `human_query` matches `/LLM error|404|自动调查未完成/`.

**Allowed identification (priority order):**

1. Join `HumanReviewRequest.investigation_id` → Investigation with structured `failure_class` in ops set **or** status FAILED/DEGRADED with ops error_code set by new code.  
2. Join via Event’s investigations: if the HR’s investigation has an invalidated ops conclusion mark.  
3. For **legacy** rows without structured fields: candidate list for **admin review queue** (suggested by heuristics including regex + verdict/reasoning patterns) — **human confirms** before cancel.  
4. Never auto-cancel when Investigation is missing or linkage ambiguous.

**On confirmed ops-related cancel:**

- Status → `CANCELLED` (existing enum).  
- Persist `cancel_reason` (e.g. `ops_failure_reclassification`), actor (`system` or admin id), timestamp.  
- Retain `question`, `context_summary`, `sent_at`, `external_msg_id`, responses.  
- Investigation row retained; Conclusion row retained; set invalidation mark + reason (not DELETE).

**Tests T-HR-CLEAN-01..05:** linked ops inv cancels with reason; ambiguous row stays for admin; regex-only does not cancel; conclusion still readable with invalidation flag; re-run does not resurrect cancelled HR.

---

### Task P0-05 — Investigation conclusion protection

| Field | Content |
|-------|---------|
| **Task ID** | P0-05 |
| **Severity** | Critical |
| **Current** | Closure/supervisor exist; max_steps/skill/closure-retry still use `degraded_conclusion` → HR |
| **Code paths** | `loop.py` L139–145, L189–192, L243–244; orchestrator supervisor L258–260 |
| **Required changes** | Enforce matrix: ops vs security incomplete; optional skill ≠ global FAILED; never unsupported attack/FP; record missing evidence |
| **DB impact** | Shared with P0-03 |
| **API impact** | Trace shows failure_class + missing evidence |
| **Migration** | With P0-03 |
| **Regression risks** | Over-classifying security gaps as ops |
| **Test cases** | T-FAIL-03..08, T-FAIL-10 |
| **Acceptance** | Spec P0-05 + matrix rules |
| **Rollback** | Shared flag with P0-03 |

---

### Task P0-01 — Default admin account security (+ MFA upgrade)

| Field | Content |
|-------|---------|
| **Task ID** | P0-01 |
| **Severity** | Critical |
| **Current** | Defaults changeme / weak JWT; UI leak; change-password exists; no force/rate-limit/token_version |
| **Code paths** | `config.py` L39,71–73; `009_console_seed.py` L36–46; `LoginPage.tsx` L199; `auth.py` login/change-password; `create_access_token` L46–67 |
| **Required changes** | §6 Admin Bootstrap + MFA enrollment compatibility |
| **DB impact** | `must_change_password`, `token_version`, optional `mfa_enrollment_deadline` / `mfa_grace_until` for legacy admins |
| **API impact** | Login flags; block admin mutations until password+MFA complete; all protected routes check `token_version` |
| **Migration** | Additive; no password hash reset; weak-password detection → force change; MFA controlled enroll |
| **Regression risks** | Lockout; automation JWT; single-admin MFA trap |
| **Test cases** | Prod refuse weak secrets; force password change; JWT invalid after change/**all** `require_auth` paths honor `tv`; rate limit 429; new admin cannot call admin APIs until MFA enrolled; legacy admin grace path; second-admin reset audited; single-admin break-glass dry-run documented |
| **Acceptance** | Spec P0-01 + D-AUTH-* + D-MFA-* + §6.7 acceptance + §6.8 rollback |
| **Rollback** | **See §6.8** — production must not restore changeme / weak JWT; no env kill-switch for auth |

---

### Task P0-08 — Configuration and security audit

| Field | Content |
|-------|---------|
| **Task ID** | P0-08 |
| **Severity** | High |
| **Current** | `update_config` unaudited (`system.py` L38–53) |
| **Required changes** | before/after redacted audit; correlation id; cover high-value mutations |
| **DB impact** | Optional additive `correlation_id` / `result` on `audit_logs` |
| **API impact** | Richer audit filters |
| **Migration** | Additive nullable |
| **Rollback** | Stop writing new fields |
| **Test cases** | Config PUT → audit with before/after; secrets redacted |
| **Acceptance** | Spec P0-08 |

---

### Task P0-02 — Pilot residual + Legacy / Scoped API keys

| Field | Content |
|-------|---------|
| **Task ID** | P0-02 |
| **Severity** | High |
| **Current** | Env API key → full admin (`deps.py` L47–58); `api_keys` table unused by auth; Pilot MFA default off |
| **Required changes** | Pilot MFA default on; route matrix; **Legacy API key policy §7**; Scoped keys; high-risk JWT-admin-only (O-07 Proposed); Operator by pipeline type (O-10 Proposed) |
| **DB impact** | Extend `api_keys` with scopes, legacy flag; wire verify path |
| **API impact** | Key CRUD; migration guide; deprecation audits |
| **Migration** | Compatibility window **Proposed 30 days (O-02)** — final end date needs PO approval |
| **Rollback** | Re-enable legacy accept flag without restoring high-risk on legacy key |
| **Test cases** | Legacy use audited; legacy blocked from high-risk; scoped key limited; disable legacy; pilot MFA default; **T-KEY-01..09** (§7.3) |
| **Acceptance** | Spec P0-02 + D-KEY-* + §7.3 |

---

### Task P0-04 — Status and verdict semantics

| Field | Content |
|-------|---------|
| **Task ID** | P0-04 |
| **Severity** | Medium |
| **Status** | **COMPLETED** (2026-11-06) — closure: `docs/review/P0_04_CLOSURE.md`; glossary: `docs/review/STATUS_VERDICT_SEMANTICS.md` |
| **Required changes** | Glossary; independent Investigation Status vs Security Verdict vs Severity vs Analyst Priority vs Evidence Strength; no risk→verdict; O-03 Event `pending_review` + block auto-pick preserved from P0-03 |
| **DB impact** | Prefer **no** new Event status (O-03 Option A). Wired existing nullable `evidence_strength` / `disposition_grade` (migration 018); **no destructive rewrite** of historical conclusions |
| **API impact** | List/detail expose independent dimensions; active security verdict null for ops FAILED / invalidated |
| **Migration** | None new for P0-04; additive columns already present |
| **Rollback** | Stop writing new dimension fields; historical rows retained |
| **Test cases** | `tests/agent/test_semantics_p0_04.py` + ops-failure / conclusion suites |
| **Acceptance** | Spec P0-04 — see acceptance table below |

#### P0-04 acceptance results (reported)

| Requirement | Result |
|-------------|--------|
| COMPLETED + BENIGN / MALICIOUS / INCONCLUSIVE | **PASS** |
| FAILED investigation has no active security verdict | **PASS** |
| HIGH severity + BENIGN; LOW severity + MALICIOUS | **PASS** |
| INCONCLUSIVE is never silently converted to BENIGN | **PASS** |
| System failures do not fabricate security conclusions | **PASS** |
| API exposes independent semantic dimensions | **PASS** |
| Frontend distinguishes status/verdict/severity/priority/evidence | **PASS** |
| No risk-to-verdict derivation | **PASS** |
| Historical records are not rewritten | **PASS** |
| Browser end-to-end verification | **NOT TESTED** |
| Real DB integration tests for list/detail | **NOT TESTED** |

#### P0-04 test results (reported)

| Suite | Result |
|-------|--------|
| Focused (`tests/agent` + `human_review` + `console`) | **102 passed** |
| Full test suite | **209 passed / 13 failed** |

#### Full-suite residual failures (test debt — not claimed as independently verified baseline in this closure)

Categories reported failing in the full-suite run:

- `test_event_key`
- `test_config`
- `test_query_threat_intel_timezone`
- `test_audit_p0_08` × 5 (requires real DB integration environment)
- `test_models`
- `test_is_public_ip`
- `test_dedup` × 2
- `test_frequency_datetime`

**Note:** A related set of **8** failures was documented earlier at P0-08 close (`P0_08_PREEXISTING_FAILURE_BASELINE.md`). The **13** failures above are recorded as **test debt**. Do **not** describe all 13 as definitively pre-existing unless a dedicated baseline re-run confirms overlap. Confirmed vs unverified baseline status remains distinguished in `P0_04_CLOSURE.md`.

#### Residual design (documented; not changed at closure)

- **`disposition_grade`:** response-priority mapping from Verdict + Risk — **not** a second verdict; must not overwrite Verdict; mapping remains documented/testable.
- **Event queue `VERDICT_EVENT_STATUS`:** workflow routing only (e.g. INCONCLUSIVE → `HUMAN_PENDING`); separate from Investigation Status; must not overwrite Security Verdict; `HUMAN_PENDING` ≠ malicious.

---


### Task P0-06 — Data flow and privacy

| Field | Content |
|-------|---------|
| **Task ID** | P0-06 |
| **Severity** | High |
| **Status** | **A..E code complete; PO conditional acceptance** (2026-11-06). Evidence review in `P0_06_AE_IMPLEMENTATION_REPORT.md` §验收-* / §10. **P1/P2 (F..N) NOT started.** |
| **Done (A..E)** | Disclosure; EgressGateway; LLM/TI/WeCom/Embed/Webhook; `privacy.*`; contract tests + bypass script |
| **Remaining (not authorized)** | F..N; runtime RV-01..08; browser E2E |
| **DB/API** | No Alembic for A..E. Privacy APIs + system_config seeds |
| **Tests (acceptance re-run)** | privacy **16 passed**; combined **118 passed**; full **225 passed / 13 failed / 0 skipped** (8 match P0-08 baseline doc; 5 audit integration = missing `api_keys.scopes` schema) |
| **Acceptance** | Automated matrix mostly PASS/PARTIAL; **runtime network = NOT TESTED**; **E2E = NOT TESTED** — must not mark PASS |
| **Must not claim** | Air-gap / “alerts never leave” without verified egress controls |

#### P0-06 batches

| Batch | Status |
|-------|--------|
| P0 A..E | **Done** — wait PO acceptance |
| P1 F..J | **Not started** (needs separate auth) |
| P2 K..N | **Not started** |

Open PO questions remain: O-08, O-09, Q-DATA-01..05 — **not** Confirmed.

---

### Task P0-07 — Internationalization

| Field | Content |
|-------|---------|
| **Task ID** | P0-07 |
| **Severity** | High |
| **Required changes** | Extract hardcoded zh; remove credential hints; error codes |
| **DB** | None |
| **Migration** | N/A |
| **Rollback** | Per-page |
| **Test cases** | EN walk / CI grep CJK outside zh dict |
| **Acceptance** | Spec P0-07 |

---

### Task P0-09 — Whitelist promotion / suppression safety

| Field | Content |
|-------|---------|
| **Task ID** | P0-09 |
| **Severity** | High |
| **Current** | N confirms → ACTIVE rule → triage auto-archive (`promoter.py` L40–73; `whitelist.py` L39–51) |
| **Required changes** | Separate confirm vs suppression; default suppress off; admin per-rule enable; TTL/revoke; queryable suppressed alerts |
| **DB impact** | `suppression_enabled` default false; approval actor/timestamps; retain rule rows |
| **API impact** | enable-suppression admin-only; revoke |
| **Migration** | O-04 Proposed: all existing ACTIVE → `suppression_enabled=false`; keep rule data + audit_trail |
| **Regression risks** | Alert volume spike |
| **Test cases** | Confirm≠suppress; admin enable audited; expire/revoke; alerts queryable |
| **Acceptance** | D-WL-* |
| **Rollback (revised — mandatory)** | See §8 — **must not** restore global auto-suppression |

---

## 6. Admin Bootstrap & MFA upgrade (P0-01 detail)

### 6.1 Production start gate

Refuse start in production if weak/missing `JWT_SECRET`, weak/missing admin bootstrap secret when creating admin, weak default `API_KEY` (ties to P0-02). Never log initial password.

### 6.2 Answers: first credentials & no TOTP circular dependency

| Question | Answer (based on current code + planned delta) |
|----------|-----------------------------------------------|
| How does a new admin get first login credentials? | Operator sets strong `ADMIN_INITIAL_PASSWORD` / Docker Secret at deploy; bootstrap creates `admin` with bcrypt hash. Password is **not** printed to app logs. Operator receives it only via secret store / out-of-band handoff. |
| How to get a short-lived restricted token for password change + MFA enroll only? | After successful **password** auth, if `must_change_password` and/or (`mfa_required` && `mfa_secret is null`), issue a **bootstrap access token** (JWT) with claim e.g. `tok="bootstrap"` / `scopes=["auth.change_password","auth.mfa_enroll","auth.me"]`, short TTL (e.g. 15–30 min), includes `tv`. **Alternatively** continue using existing MFA challenge token (`typ=mfa`, `purpose=setup`) for the TOTP step only — see flow below. |
| How is that token blocked from normal Admin APIs? | `require_auth` / `require_admin` / `require_write`: if `tok==bootstrap` (or missing full-session mark), allow **only** allowlisted paths (`POST /auth/change-password`, `POST /auth/mfa/verify`, `GET /auth/me`). All other `/api/v1/**` → **403**. Frontend hiding buttons is **not** sufficient. |
| Enrollment interrupted / MFA token timeout? | Current `MFA_TOKEN_TTL_MINUTES=5` (`app/services/mfa.py`). On expiry: user **re-enters password** on `/auth/login`; if still not enrolled, server issues a **new** `purpose=setup` challenge with a **new** `pending_secret` (old pending discarded). No need for completed TOTP to restart setup. |
| How do legacy admins upgrade MFA? | Set `mfa_required=true`; optional `mfa_grace_until`. Same **setup** path when `mfa_secret is null`. Grace allows bootstrap-scoped access only (not high-risk admin). |
| Last-admin lockout? | **Must not** occur: while any admin has `mfa_required && mfa_secret is null`, login always offers setup path; never require `purpose=verify` without a stored secret. Hard-lock of login is forbidden if zero admins have `mfa_secret`. Break-glass (O-05) for lost device after enroll. |

**Critical — no circular dependency:**  
Existing code already branches correctly (`auth.py` L145–187): `mfa_required && mfa_secret` → verify; `mfa_required && !mfa_secret` → **setup** with QR/`pending_secret` in MFA token. **Never** require a prior TOTP code to start enrollment. P0-01 must preserve this branch.

### 6.3 Target enrollment flow (new admin)

```text
[Operator] sets ADMIN_INITIAL_PASSWORD (secret)
    → [Bootstrap] create admin: must_change_password=true, mfa_required=true, mfa_secret=null
[Admin] POST /auth/login {username, password}
    → password OK
    → if must_change_password:
         issue bootstrap JWT (scopes: change_password, mfa_enroll, me)  OR force change-password before MFA
    → POST /auth/change-password  (bootstrap JWT)
         → token_version++; must_change_password=false; re-issue bootstrap or continue
    → if mfa_required && mfa_secret is null:
         POST /auth/login again OR continue session → response mfa_setup_required + mfa_token(purpose=setup) + QR
         (NO full admin access_token yet)
    → User scans QR, POST /auth/mfa/verify {mfa_token, code}
         → persist mfa_secret; issue **full** access_token (tok=session)
    → Full Admin APIs allowed
```

If password already changed and only MFA pending: login → setup challenge directly (existing path).

### 6.4 Legacy admin controlled enrollment (no lockout)

1. On upgrade: set `mfa_required=true` for admins **without** wiping `mfa_secret` or passwords.  
2. Optional `mfa_grace_until`: login works; mutations that are high-risk blocked until enrolled; enroll endpoints always allowed.  
3. After grace: block **admin mutations** until enrolled; **still** allow login + setup.  
4. If **zero** admins have `mfa_secret`: never refuse login/setup; show critical banner; enable O-05 break-glass.  
5. Do **not** bulk-reset passwords (D-AUTH-07).

### 6.5 API permission matrix (enrollment vs full admin)

| Endpoint / class | Unauthenticated | MFA challenge token (`typ=mfa`) | Bootstrap JWT | Full session JWT (admin, enrolled) |
|------------------|-----------------|----------------------------------|---------------|-------------------------------------|
| `POST /auth/login` | Yes | — | — | — |
| `POST /auth/mfa/verify` | Yes (with mfa_token) | Yes | Yes (if used) | — |
| `POST /auth/change-password` | No | No | **Yes** | Yes |
| `GET /auth/me` | No | No | **Yes** (flags only) | Yes |
| Dashboard / events read | No | No | **No** | Yes |
| System config / users / license / suppression enable | No | No | **No** | Yes (`require_admin`) |
| Pipeline write / disposition | No | No | **No** | Yes (`require_write` / admin as designed) |

### 6.6 token_version

- JWT claim `tv` must match `users.token_version` in **every** path that accepts Bearer tokens (`require_auth` and wrappers).  
- Increment on: password change, MFA reset/reissue, admin revoke, explicit session revoke.  
- Bootstrap and full tokens both carry `tv`.  
- **Acceptance:** route audit — no protected router skips `tv` check.

### 6.7 Single-admin MFA loss (O-05 Proposed)

1. Preferred: second admin `POST /users/{id}/mfa/reset` (audited) → setup path again.  
2. Single admin: **time-limited** break-glass (ops procedure / one-time secret): clears `mfa_secret`, forces re-enroll + optional password change, immutable audit, `token_version++`, expires automatically.  
3. Backup codes: **Not Found** in v1 unless PO expands O-05.

### 6.8 P0-01 Rollback strategy (strengthened)

| Rule | Requirement |
|------|-------------|
| Weak defaults | Production rollback **must not** restore `changeme` or weak `JWT_SECRET`. Start-gate remains. |
| token_version | Invalidation mechanism **must not** be bypassable by rollback of “convenience” flags; old JWTs with stale `tv` stay rejected. |
| MFA emergency recovery | Only via audited, **time-limited** break-glass; forces re-bind; not a permanent MFA off switch. |
| DB columns | Additive columns (`must_change_password`, `token_version`, grace fields) **retained**; no destructive down-migration that drops security columns in prod. |
| Kill switch | **Forbidden:** ordinary env var that disables all auth hardening (`DISABLE_AUTH_SECURITY=true` or similar). Dev-only `ALLOW_INSECURE_DEFAULTS` must refuse to activate when `APP_ENV=production`. |

### 6.9 MFA / bootstrap test cases

| ID | Scenario | Expect |
|----|----------|--------|
| T-MFA-01 | New admin first login, no TOTP yet | `mfa_setup_required` or bootstrap path; **not** `mfa_required` verify-only |
| T-MFA-02 | Bootstrap JWT calls `PUT /system/config` | 403 |
| T-MFA-03 | Bootstrap JWT `change-password` then MFA setup+verify | Full token; admin API 200 |
| T-MFA-04 | MFA challenge token expired | Re-login issues new setup; no circular verify demand |
| T-MFA-05 | Legacy admin in grace, not enrolled | Cannot enable suppression / user admin; can enroll |
| T-MFA-06 | Zero admins enrolled | Login+setup still works; no hard lockout |
| T-MFA-07 | Password change increments `tv`; old JWT | 401 on protected API |
| T-MFA-08 | All `require_auth` routes honor `tv` | Parametrized audit test |

---

## 7. Legacy API Key + Scoped API Key (P0-02 detail)

### 7.1 During window (Proposed length: 30 days — O-02 final date TBD)

| Rule | Behavior |
|------|----------|
| Mark | Treat env `API_KEY` as **Legacy** in AuthContext (`via_legacy_api_key=true`) |
| Audit | Every authenticated call audited with legacy marker |
| Disable | Admin/config can **actively disable** legacy accept without deleting env file from hosts |
| High-risk | Legacy key **cannot** perform new high-risk ops (O-07 list) |
| Scopes | Migrate to hashed scoped keys in existing `api_keys` table |

### 7.2 Extend existing `api_keys` model (prefer over new table)

**Current (Static):** `ApiKey` has `key_hash`, `key_prefix`, `is_active`, `expires_at`, `last_used_at`, `user_id` — **not** wired into `require_auth` (`deps.py` uses env key only).

**Planned additive fields (only if missing):** `scopes` (JSONB/array), `revoked_at`, optional `rotated_from_id`. Reuse `is_active` + `revoked_at` for revoke-immediate.

### 7.3 Scoped API Key acceptance criteria (mandatory)

| ID | Criterion |
|----|-----------|
| T-KEY-01 | DB stores **hash only** (`key_hash`); plaintext never persisted |
| T-KEY-02 | Plaintext returned **once** on create (and once on rotate); never on GET list/detail |
| T-KEY-03 | `expires_at` enforced in auth; expired → 401 |
| T-KEY-04 | `revoked_at` / `is_active=false` → **immediate** 401 (no wait for TTL) |
| T-KEY-05 | Rotate: new row (or new hash) + revoke old; old secret fails immediately |
| T-KEY-06 | Logs/audit **must not** contain plaintext key or full Authorization secret |
| T-KEY-07 | Scopes **cannot** elevate to full Admin; no scope alias that implies `role=admin` |
| T-KEY-08 | Legacy env key **cannot** execute high-risk ops (O-07) even during compatibility window |
| T-KEY-09 | Prefix shown for support (`key_prefix`); sufficient to identify, not to authenticate |

### 7.4 Migration steps (operator runbook)

1. Create scoped API key via admin API; store secret once.  
2. Update automation `X-API-Key` to new key.  
3. Verify scoped permissions (positive + negative).  
4. Disable legacy accept.  
5. Rotate away env `API_KEY` from secret store.  
6. After PO-approved deadline: production refuses legacy key.

### 7.5 After window

Legacy denied in production; scoped keys + JWT only.

### 7.6 Rollback

May re-enable legacy **accept** for emergency automation **without** restoring high-risk privileges on legacy key.

---

## 8. P0-09 rollback strategy (revised)

**Forbidden:**

- Ordinary rollback / feature flag that restores **global** auto-suppression on candidate confirm.  
- Environment variable that bypasses per-rule admin approval (D-WL-07).

**Required rollback behavior:**

1. After any rollback of code/migration helpers, **`suppression_enabled` remains default false**.  
2. Rules and approval history **retained**; statuses and `approved_by` / timestamps remain queryable.  
3. Re-enabling suppression = **admin per-rule approval** only.  
4. Triage continues to record whitelist hits; archived/suppressed alerts remain searchable and auditable.  
5. If a hotfix must temporarily change matcher behavior, it still must not auto-enable suppress on confirm.

---

## 9. Investigation failure & Event auto-pick (aligned O-03 Proposed)

| Case | Investigation | Conclusion | Event | HR |
|------|---------------|------------|-------|-----|
| LLM / required skill / datasource ops fail | FAILED (+ failure_class) | None or invalidated if legacy | `pending_review`; **not auto-picked** | No |
| Optional skill fail | Continue / DEGRADED evidence | Per matrix | Normal pipeline | Only if security gap |
| Security / business context gap | NEEDS_HUMAN | Real security conclusion | human_pending | Yes |
| Success | COMPLETED | Verdict | concluded/… | Per verdict |

Re-run: **new** Investigation ID; never overwrite old tool_calls/conclusions.

### 9.1 Backend auto-pick / manual re-run requirements

**Current code (Static):** `InvestigationOrchestrator._pick_events` (`orchestrator.py` L188–203) selects `Event.status == PENDING_REVIEW` and excludes events that have **any** Investigation in `RUNNING` or `COMPLETED`. It does **not** inspect “latest” Investigation for `FAILED`. Therefore, after an ops `FAILED` with Event left in `pending_review`, the scheduler **would auto re-pick today** — this is the gap O-03 / P0-03 must close.

**Required behavior:**

1. **Auto-pick must evaluate the latest Investigation** for the Event (order by `started_at` / `created_at` desc).  
2. If latest Investigation is ops `FAILED` (or ops `DEGRADED` per matrix) → **exclude** from auto-pick.  
3. Admin **explicit re-run** API creates a **new** Investigation row (new UUID); does not mutate the failed row.  
4. **Concurrency / idempotency:**  
   - Reuse existing Redis `investigate_lock` (`app/agent/lock.py`) for batch auto runs.  
   - Manual re-run: acquire same global lock **or** add per-event Redis lock `investigate:event:{event_id}` (prefer reuse global first; per-event only if needed for UX latency).  
   - Before insert: assert no `RUNNING` Investigation for that `event_id`; if race, return 409 / skip (idempotent).  
5. **Backend enforcement:** re-run requires `require_admin` (or PO-approved role); state checks on server. Frontend hiding “Re-run” is **not** authorization.  
6. Successful re-run after fix: new Investigation proceeds; old FAILED retained.

### 9.2 Do we need a new DB field on Event?

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| A. Filter in `_pick_events` using latest Investigation `status` + planned `failure_class` | No Event schema change; aligns with D-PROC-03 | Query slightly heavier (subquery/window) | **Preferred** if O-03 accepted |
| B. Event flag e.g. `auto_investigate_blocked` | Simple pick predicate | Extra field + migration; must stay in sync with Investigation | Only if query A proves too costly / unclear |
| C. New EventStatus `ops_blocked` | Explicit | Broader enum/UI impact; PO preferred avoiding Event terminal FAILED | Avoid unless A/B insufficient |

**Conclusion:** Prefer **Option A — no new Event column** for auto-pick control. Use Investigation fields already planned for P0-03 (`status=FAILED`, `failure_class`). Revisit B only with evidence. **UNKNOWN** until implementation profiling if subquery performance needs an index-only helper column.

### 9.3 Auto-pick / re-run tests

| ID | Scenario | Expect |
|----|----------|--------|
| T-PICK-01 | Latest inv ops FAILED; Event pending_review | Auto `_pick_events` does **not** return Event |
| T-PICK-02 | Admin re-run | New Investigation id; old FAILED unchanged |
| T-PICK-03 | Concurrent auto + manual re-run | One RUNNING via lock; no duplicate RUNNING |
| T-PICK-04 | Re-run while RUNNING exists | Rejected / no second RUNNING |
| T-PICK-05 | Non-admin calls re-run API | 403 (backend) |
| T-PICK-06 | After successful new COMPLETED | Event leaves ops-blocked pick behavior per verdict mapping |

---

## 10. Data flow inventory

**Authoritative Phase 1 audit:** `docs/review/P0_06_DATA_FLOW_AUDIT.md` (v1.0.1).

Summary (Static): full Wazuh `raw_data` stored locally; investigation LLM transmits **derived** alert fields + SOP/HR/tool summaries to `{DEEPSEEK_BASE_URL}/chat/completions` when key set (default URL `api.deepseek.com`); TI sync may send public IPs to AbuseIPDB/GreyNoise when keys set; WeCom HR markdown may egress host/user/reasoning; embeddings optional (default off); product telemetry **Not Found**. Customer-facing `DATA_FLOW.md` still to publish under P0-06 **implementation**. BYO endpoint + embedding default off remain O-08/O-09 **Proposed**.

---

## 11. P1 summary

Unchanged order; Timeline + Evidence share IDs; justify tables before creating; expand full schema at kickoff.

---

## 12. Consistency checklist (v1.2.4)

| Check | Status |
|-------|--------|
| P0 order identical in AUDIT / PLAN / DECISIONS | Yes — §1 / audit §10 / D-ORD-01 |
| P1 order identical | Yes |
| Every P0 has tests + acceptance | Yes — §5 + T-FAIL / T-HR-CLEAN / T-PICK / T-MFA / T-KEY + P0-04 table; P0-06 acceptance deferred until implementation |
| Every DB change has upgrade + rollback | Yes — per task + §5.1, §6.8, §8 |
| P0-09 rollback forbids global auto-suppress restore | Yes — §8 |
| P0-01 rollback forbids weak-secret restore / auth kill-switch | Yes — §6.8 |
| HR cleanup not regex-only | Yes — §5.1 |
| Skill matrix + tests | Yes — §4 |
| Event auto-pick prefers no new Event column | Yes — §9.2 Option A |
| MFA setup without prior TOTP (no circular dep) | Yes — §6.2 |
| Scoped key acceptance T-KEY-01..09 | Yes — §7.3 |
| P0-04 status/verdict independence + acceptance recorded | Yes — §5 Task P0-04 / `P0_04_CLOSURE.md` / `STATUS_VERDICT_SEMANTICS.md` |
| P0-04 full-suite 13 residuals not claimed independently verified baseline | Yes — §5 + `P0_04_CLOSURE.md` |
| P0-06-A..E implemented + evidence reviewed; runtime/E2E not PASS; P1/P2 not started | Yes — §5 / `P0_06_AE_IMPLEMENTATION_REPORT.md` v验收核对 |

---

## 13. Top regression hotspots

1. AgentLoop/orchestrator failure classification  
2. Historical HR cleanup false positives/negatives  
3. token_version + MFA grace lockout  
4. Legacy API key cutover  
5. Whitelist suppression off → alert volume  

---

## 14. Still blocking development

**O-01 CONFIRMED** — removed from blocking list.

Until PO final confirmation (see `PRODUCT_OWNER_DECISIONS.md` §D):

1. **O-02** — Legacy API_KEY final deadline (30-day plan is Proposed only)  
2. **O-03** — Event `pending_review` + block auto-pick + explicit re-run  
3. **O-04** — disable suppression on all existing ACTIVE rules  
4. **O-05** — single-admin MFA break-glass for v1  
5. **O-07 / O-10** — high-risk JWT-admin list + Operator pipeline matrix  

---

## 15. Stop

Plan **v1.2.10**: R-A + R-B complete. **Do not** start AUTH-R4/R6、AUTH-R5、F..N、P0-07、P0-09、or P1 without explicit PO authorization.
