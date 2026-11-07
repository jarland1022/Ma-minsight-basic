# Status / Verdict semantics glossary (P0-04)

Canonical terminology for MinSight. Do not conflate these dimensions.

## Dimensions

| Dimension | Meaning | Primary storage | Example values |
|-----------|---------|-----------------|----------------|
| **Event status** | Event workflow / queue state | `events.status` (`EventStatus`) | `pending_review`, `investigating`, `human_pending`, `concluded`, `closed` |
| **Investigation status** | Investigation run workflow | `investigations.status` (`InvestigationStatus`) | `running`, `completed`, `failed`, `needs_human`, `degraded` |
| **Security verdict** | Evidence-supported security conclusion | `investigation_conclusions.verdict` | `attack_confirmed`, `likely_false_positive`, `insufficient_information`, `needs_human_review` |
| **Severity / risk level** | Impact seriousness of the case | `investigation_conclusions.risk_level` (+ event `risk_score`) | `critical`/`high`/`medium`/`low` |
| **Analyst priority** | Urgency of human attention / response | event `queue_priority`; optional `disposition_grade` | numeric priority; grades below |
| **Evidence strength** | Sufficiency/quality of supporting evidence | `investigation_conclusions.evidence_strength` | `multi_path`, `single_path`, `none` |
| **Failure class** | Ops vs security-gap classification | `investigations.failure_class` | `llm_service`, `required_skill`, … |

## Hard rules

1. `InvestigationStatus.COMPLETED` does **not** imply `likely_false_positive` (benign).
2. `InvestigationStatus.FAILED` does **not** imply `insufficient_information` and must **not** invent a security verdict.
3. High `risk_level` / `risk_score` does **not** imply `attack_confirmed`.
4. `insufficient_information` must never be silently rewritten to `likely_false_positive`.
5. Ops/infrastructure failure (`failure_class` in ops set) must not create an active security conclusion (P0-03/P0-05).
6. Missing evidence is not evidence of benign behavior.
7. A completed investigation may have `insufficient_information` (inconclusive). Event may still be `human_pending`.
8. Event status may be driven by verdict for **queue routing only** (`VERDICT_EVENT_STATUS`); that must not overwrite investigation workflow status.

## Documented derivation (allowed)

| Derived field | Inputs | Rule |
|---------------|--------|------|
| `events.status` after a successful conclusion | `verdict` | Routing map only — see `VERDICT_EVENT_STATUS` |
| `evidence_strength` | evidence_refs count + closure score | Independent of verdict |
| `disposition_grade` (optional) | `verdict` + `risk_level` | Response-priority hint; **not** a second verdict |

### `disposition_grade` invariants

- Must **not** modify or overwrite the original Security Verdict.
- Must **not** be presented as a security verdict in UI/API primary labeling.
- Mapping must remain documented and testable (`app/agent/semantics.py`, unit tests).

### Event queue routing invariants (`VERDICT_EVENT_STATUS`)

- Event queue workflow routing only (example: inconclusive → `HUMAN_PENDING`).
- Separate from Investigation Status.
- Must **not** change the original Security Verdict.
- `HUMAN_PENDING` does **not** mean malicious or confirmed attack.
- New Verdict values require an explicitly reviewed queue-routing policy.

## O-03 (Event after ops FAILED)

Keep Event at `pending_review`. Auto-pick blocked by latest Investigation `FAILED`/`DEGRADED`+ops `failure_class`. No new Event status column.

## Terminology aliases (user / tests)

| Informal | Canonical enum |
|----------|----------------|
| BENIGN | `likely_false_positive` |
| MALICIOUS | `attack_confirmed` |
| INCONCLUSIVE | `insufficient_information` |
