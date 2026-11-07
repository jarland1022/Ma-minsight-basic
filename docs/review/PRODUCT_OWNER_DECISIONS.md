# Product Owner Decisions Log

**Version:** 1.2.3  
**Date:** 2026-11-06  
**Scope:** Decisions from PO round-2/3 + Prompt 04 + **O-01 CONFIRMED** + P0-04 semantic acceptance record  
**Status:** Binding confirmed items + **Proposed** items awaiting final PO confirmation  
**Constraint:** Docs-only updates for this closure pass (no application code/DB/config changes in the closure task)  

**Round-3 applied:** canonical P0 order; D-FAIL-09..12; D-WL-07; D-AUTH-10/11 + D-KEY-04; O-02…O-10 **Proposed**.  

**Prompt 04 applied:** Event auto-pick prefers Investigation-based filter; MFA bootstrap; P0-01 rollback; Scoped API Key T-KEY-01..09.  

**O-01 CONFIRMED:** No publicly accessible MinSight instance today (local / customer private networks only). Emergency P0-01 queue-jump **not** required; normal order P0-03 → P0-05 → P0-01.  

**v1.2.3:** P0-04 Status and verdict semantics — implementation acceptance recorded; semantic boundaries below are **Proposed clarifications** for formal PO stamp where not already Confirmed under D-FAIL-*.  

---

## A. Confirmed decisions

### A1. Document / process

| ID | Decision |
|----|----------|
| D-PROC-01 | Planning phases revise docs only until PO final approval to implement. |
| D-PROC-02 | Prefer extending existing models/services/APIs; do not rebuild satisfied modules. |
| D-PROC-03 | Do not add DB tables solely because the product spec suggested them; justify each migration. |
| D-PROC-04 | Every DB migration task must include upgrade + rollback + customer-data compatibility. |
| D-PROC-05 | Do not treat PO suggestions as already implemented. Mark unresolved items UNKNOWN / Proposed. |

### A2. P0 / P1 ordering (v1.2 — unified across all three docs)

| ID | Decision |
|----|----------|
| D-ORD-01 | **P0 order (canonical):** 1 P0-03 → 2 P0-05 → 3 P0-01 → 4 P0-08 → 5 P0-02 → 6 P0-04 → 7 P0-06 → 8 P0-07 → 9 P0-09. |
| D-ORD-02 | **Historical contingency (not active now):** If a deployment were internet-exposed, P0-01 would be an immediate emergency ahead of P0-03/05. **O-01 CONFIRMED:** no public instance today → **do not** emergency queue-jump. Normal order: P0-03 → P0-05 → P0-01. P0-01 remains P0 and **must** complete before formal production customer deploy. Any future public exposure requires a dedicated external-exposure security assessment first. |
| D-ORD-03 | P0-03 and P0-05 are designed and tested as a continuous pair. |
| D-ORD-04 | P0-09 (Whitelist promotion / suppression safety) is in P0. |
| D-ORD-05 | P1 order: P1-01 → P1-04 → P1-05 → P1-03 → P1-02 → P1-06 → P1-07 → P1-08. |
| D-ORD-06 | Investigation Timeline has priority over Morning Briefing. |
| D-ORD-07 | Timeline and Evidence Ledger must share traceable relationships. |

### A2b. P0-04 semantic boundaries (implementation acceptance record)

The following boundaries were applied in P0-04 implementation and are recorded for PO awareness.  
They are **not** newly invented Confirmed decision IDs. Where not already covered by existing D-FAIL-* Confirmed items, treat them as **Proposed clarifications** until PO formally stamps them. Evidence: `STATUS_VERDICT_SEMANTICS.md`, `P0_04_CLOSURE.md`, `IMPLEMENTATION_PLAN.md` §5 Task P0-04.

1. **Workflow status and security verdict remain independent.** Investigation Status is workflow execution state; Security Verdict is an evidence-supported conclusion.
2. **Severity, analyst priority, and evidence strength remain separate dimensions** and must not be silently equated to Verdict.
3. **`disposition_grade` is a response-priority mapping (Verdict + Risk), not a second verdict.** It must not overwrite Verdict or be presented as a security conclusion.
4. **Event queue routing (`VERDICT_EVENT_STATUS`) is independent of Investigation Status** and must not overwrite Security Verdict. Example: `INCONCLUSIVE` → Event `HUMAN_PENDING` is queue routing only; `HUMAN_PENDING` does not mean malicious.
5. **Historical conclusions must not be silently rewritten** (no destructive backfill of invented verdicts).
6. **Browser E2E and real DB integration verification remain outstanding (NOT TESTED)** for P0-04 acceptance.

### A3. Admin bootstrap & session security (P0-01)

| ID | Decision |
|----|----------|
| D-AUTH-01 | Production must use explicitly configured strong initial password or Docker Secret. |
| D-AUTH-02 | Default `changeme` is forbidden. |
| D-AUTH-03 | Weak default `JWT_SECRET` is forbidden in production. |
| D-AUTH-04 | Missing valid init credentials → production **refuse to start**. |
| D-AUTH-05 | Initial password must **not** be printed to ordinary application logs. |
| D-AUTH-06 | First login must force password change. |
| D-AUTH-07 | Existing deployments need a **compatible migration**; must **not** bulk-reset customer passwords. |
| D-AUTH-08 | After password change, old JWTs must become invalid (`token_version`). |
| D-AUTH-09 | Login rate limiting is mandatory. |
| D-AUTH-10 | New admins must complete MFA enrollment; incomplete MFA blocks admin operations (see plan). |
| D-AUTH-11 | Legacy admins use a controlled MFA enrollment path that cannot lock out the last admin. |
| D-AUTH-12 | MFA enrollment must use setup path when `mfa_secret` is null — **no** require-verify-before-enroll circular dependency. |
| D-AUTH-13 | Bootstrap/restricted tokens cannot call normal Admin APIs; backend allowlist only. |
| D-AUTH-14 | P0-01 rollback must not restore changeme/weak JWT_SECRET; must not bypass `token_version`; must not provide a production env kill-switch for auth hardening; DB security columns are not destructively dropped. |

### A4. MFA

| ID | Decision |
|----|----------|
| D-MFA-01 | Production admins **must** have MFA enabled. |
| D-MFA-02 | Pilot Viewer accounts **default** to MFA required. |
| D-MFA-03 | Prefer existing TOTP + admin reset/reissue APIs; do not re-build MFA if gaps are only policy/enforcement. |

### A5. API keys & authorization

| ID | Decision |
|----|----------|
| D-KEY-01 | Do **not** keep a default full-privilege shared API key as the long-term design. |
| D-KEY-02 | Do **not** delete the legacy env `API_KEY` without a compatibility window and automation impact analysis. |
| D-KEY-03 | Target design: scoped, expiring, revocable, rotatable, audited API keys. |
| D-KEY-04 | During compatibility window: legacy key is marked Legacy, audited, optionally disableable, and **blocked from new high-risk ops**. |
| D-KEY-05 | Scoped keys: hash-only at rest; plaintext once on create/rotate; `expires_at` + `revoked_at`/immediate revoke; no scope→Admin elevation; no plaintext in logs; extend existing `api_keys` model. |

### A6. Investigation / system failure (P0-03 / P0-05)

| ID | Decision |
|----|----------|
| D-FAIL-01 | System failures are Investigation / System Operation Failure — **not** security conclusions. |
| D-FAIL-02 | Investigation uses FAILED / DEGRADED independently. |
| D-FAIL-03 | System Operation Failure is recorded independently (minimal: on Investigation fields first; new table only if justified). |
| D-FAIL-04 | Do **not** create `HumanReviewRequest` for ops failures. |
| D-FAIL-05 | Do **not** fabricate `needs_human_review` conclusions for ops failures. |
| D-FAIL-06 | Do **not** set Event to a FAILED terminal status unless a clear business reason is later approved. |
| D-FAIL-07 | Preserve original alerts and failed investigation rows; repair creates a **new** Investigation; old rows not overwritten. |
| D-FAIL-08 | Retry must not duplicate Human Review tasks or silently duplicate evidence writes. |
| D-FAIL-09 | Historical HR cleanup must **not** rely solely on `human_query` regex; prefer Investigation linkage + structured error type; uncertain rows → admin review queue. |
| D-FAIL-10 | Cancelled HR retains original question, send record, and cancel reason; Investigations/Conclusions are never physically deleted for cleanup. |
| D-FAIL-11 | Confirmed ops-fault conclusions receive a traceable invalidation mark (not delete). |
| D-FAIL-12 | Skill failures follow the classification matrix (LLM / required skill / optional skill / datasource / security evidence gap / business context gap). |
| D-FAIL-13 | Auto-pick must inspect **latest** Investigation; ops FAILED blocks auto re-pick; admin explicit re-run creates new Investigation ID; Redis lock + backend authz (not UI-only); prefer **no new Event column** (filter via Investigation status/`failure_class`) unless Option A insufficient. |

### A7. Whitelist / suppression (P0-09)

| ID | Decision |
|----|----------|
| D-WL-01 | Knowledge confirmation and alert suppression must be **separated**. |
| D-WL-02 | Auto-suppression is **off by default**. |
| D-WL-03 | Enabling suppression requires **explicit admin approval** (per rule). |
| D-WL-04 | Support TTL, expiry, revoke; keep original alerts; suppressed alerts remain queryable/auditable; can re-enable normal processing. |
| D-WL-05 | Preserve existing whitelist data; evaluate compatible migration for current ACTIVE rules. |
| D-WL-06 | Prefer minimal changes to `WhitelistRule` + `WhitelistPromoter` + triage matcher. |
| D-WL-07 | Rollback must **not** restore global auto-suppression; suppression stays default-off; re-enable only via per-rule admin approval; no env var bypass of approval. |

### A8. Data flow / privacy (P0-06)

| ID | Decision |
|----|----------|
| D-DATA-01 | External model services are **not** banned by default. |
| D-DATA-02 | Data flows must be explicitly disclosed; no “alerts never leave the environment” claims without verification. |
| D-DATA-03 | Do not infer privacy from Docker topology alone. |

---

## B. Open / Proposed decisions

Status values: **CONFIRMED** | **Proposed** (written suggestion, not final until PO confirms) | **Awaiting PO**.

| ID | Topic | Status | Proposal / question |
|----|-------|--------|---------------------|
| **O-01** | Internet exposure of current deploy | **CONFIRMED** | MinSight currently has **no publicly accessible deployment**. It runs only **locally** or within **customer private networks**. Therefore: (1) P0-01 stays P0 (not downgraded); (2) **no** emergency queue-jump for public-exposure risk; (3) normal order **P0-03 → P0-05 → P0-01**; (4) P0-01 **must** be completed before formal production customer deployment; (5) any future public/internet deployment requires a dedicated external-exposure security assessment beforehand. |
| **O-02** | Legacy `API_KEY` compatibility window | **Proposed** | Tentative **30 days** from cutover announcement; final deadline **requires PO approval**. During window: Legacy mark, audit all use, allow force-disable, block new high-risk ops, publish scoped-key migration steps. |
| **O-03** | Event state after Investigation FAILED | **Proposed** | Keep Event as `pending_review`; backend **blocks auto re-pick** by inspecting **latest** Investigation (ops FAILED/`failure_class`); admin explicit re-run → **new** Investigation ID; Redis lock + idempotency. **Prefer no new Event DB field** (IMPLEMENTATION_PLAN §9.2 Option A). Confirm or request Option B flag. |
| **O-04** | Existing ACTIVE whitelist rules | **Proposed** | On upgrade, set `suppression_enabled=false` for **all** existing ACTIVE rules; admins re-approve suppression **per rule** after review. |
| **O-05** | MFA recovery model | **Proposed** | V1: second-admin `mfa/reset` or `mfa/reissue` + audit. Single-admin lost device: controlled break-glass recovery runbook (time-limited, audited, forces re-enroll) — design in P0-01; backup codes optional later. |
| **O-06** | Machine accounts | **Proposed** | Prefer **Scoped API Keys** first; do **not** build a complex Machine Account role system in P0. |
| **O-07** | High-risk operations | **Proposed** | High-risk ops are **JWT Admin only** (not legacy API key, not scoped keys unless PO later expands). Proposed list: user/MFA admin, license import, system config, enable whitelist suppression, create admin, API key admin CRUD. |
| **O-08** | BYO model endpoint | **Proposed** | Support customer-owned OpenAI-compatible endpoint via existing base URL settings; document as supported. |
| **O-09** | Embedding outbound | **Proposed** | Keep embedding **disabled by default**; enable only by explicit admin/config with disclosure. |
| **O-10** | Operator pipeline permissions | **Proposed** | Authorize Operator **by pipeline type** (not blanket all `/run` endpoints); exact matrix to be listed at P0-02 implementation kickoff and PO-confirmed. |

---

## C. Decision → plan mapping

| Decision | Plan task |
|----------|-----------|
| D-ORD-*, D-FAIL-* | P0-03, P0-05 |
| D-AUTH-*, D-MFA-*, O-01, O-05 | P0-01 |
| D-KEY-*, O-02, O-06, O-07, O-10 | P0-02 |
| D-WL-*, O-04 | P0-09 |
| D-DATA-*, O-08, O-09 | P0-06 |
| O-03 | P0-03 / P0-04 |
| P0-04 semantic boundaries (§A2b Proposed clarifications) | P0-04 |
| D-ORD-05..07 | P1 tasks |

---

## D. Still blocking development (until PO confirms)

**O-01 is CONFIRMED** — no longer blocking; emergency P0-01 insert is **not** applicable.

These items still **block or shape** implementation start:

1. **O-02** — Final Legacy API_KEY deadline (30-day plan is Proposed only)  
2. **O-03** — Confirm Event `pending_review` + block auto-pick + explicit re-run (prefer no new Event field)  
3. **O-04** — Confirm disable-all-suppression migration for existing ACTIVE rules  
4. **O-05** — Confirm single-admin MFA break-glass approach for v1  
5. **O-07 / O-10** — Final high-risk list and Operator pipeline matrix  

**Proposed** items O-06, O-08, O-09 may proceed as defaults if PO accepts them in final approval without change.
