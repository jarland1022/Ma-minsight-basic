# P0-04 Closure Record

**Date:** 2026-11-06  
**Status:** **CLOSED** (implementation + focused tests reported complete; documentation acceptance recorded)  
**Scope:** Status and verdict semantics only. **No** subsequent P0 started in this closure.  
**Companion glossary:** `docs/review/STATUS_VERDICT_SEMANTICS.md`

## Final acceptance results

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

Terminology aliases used in tests/docs: BENIGN=`likely_false_positive`, MALICIOUS=`attack_confirmed`, INCONCLUSIVE=`insufficient_information`.

## Test results (reported)

| Suite | Result |
|-------|--------|
| Focused (`tests/agent` + `human_review` + `console`) | **102 passed** |
| Full test suite | **209 passed / 13 failed** |

## Full-suite residual failures (test debt)

The following nodeid categories failed in the reported full-suite run.  
**Baseline status:** Not independently re-verified in this documentation-only closure. A related but **different** set of **8** failures was previously recorded at P0-08 close (`docs/review/P0_08_PREEXISTING_FAILURE_BASELINE.md`). Do **not** treat all 13 as confirmed pre-existing without a dedicated baseline re-run.

| Category | Notes |
|----------|-------|
| `test_event_key` | Timezone / window floor assertion |
| `test_config` | Database URL assembly expectation |
| `test_query_threat_intel_timezone` | Naive vs aware datetime |
| `test_audit_p0_08` × 5 | Integration tests; require real DB integration environment |
| `test_models` | Table registry expectation drift |
| `test_is_public_ip` | IP classification assertion |
| `test_dedup` × 2 | Naive vs aware datetime compare |
| `test_frequency_datetime` | AlertSnapshot validation / datetime |

**Tracking:** Separate hygiene / environment tickets. Do not block P0-04 documentation closure on these residuals.

## Semantic dimensions (implemented)

| Dimension | Meaning |
|-----------|---------|
| Investigation Status | Workflow execution state |
| Security Verdict | Evidence-supported security conclusion |
| Severity | Event / conclusion seriousness (`risk_level` / `risk_score`) |
| Analyst Priority | Urgency of human attention (`queue_priority`; optional `disposition_grade`) |
| Evidence Strength | Quality and sufficiency of supporting evidence |

## Residual design points (documented, not changed here)

### disposition_grade

Derived from Verdict + Risk via a **documented response-priority mapping**. It is **not** a second verdict.

Invariants:

- Must not modify or overwrite the original Verdict.
- Must not be presented as a security verdict.
- Mapping must remain documented and testable (`STATUS_VERDICT_SEMANTICS.md`, `app/agent/semantics.py`, unit tests).

### Event queue routing (`VERDICT_EVENT_STATUS`)

Example: `INCONCLUSIVE` (`insufficient_information`) → Event `HUMAN_PENDING`.

- This is **Event queue workflow routing** only.
- Separate from Investigation Status (e.g. Investigation may remain `COMPLETED`).
- Must **not** change the original Security Verdict.
- `HUMAN_PENDING` does **not** mean malicious or confirmed attack.
- New Verdict values require an explicitly reviewed queue-routing policy.

Implementation of this routing was **not** altered in this documentation task.

## Next

Per canonical order (D-ORD-01): next unimplemented P0 is **P0-06** — only after explicit PO authorization. **Not started** in this closure.
