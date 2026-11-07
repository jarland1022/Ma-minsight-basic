# P0-08 Audit Notes (R2)

## Playbook / SOP write APIs — NOT APPLICABLE

- Playbooks are a **read-only** catalog (`app/api/routes/playbooks.py` GET only).
- Investigation SOPs are listed via `GET /api/v1/console/investigation-sops`; there is **no** create/update/delete API.
- Do **not** add unrelated edit features under P0-08.

**Future requirement:** any new Playbook or SOP write API **must** call `security_audit` (fail-closed) with `event_level=business`, before/after when applicable, and must not rely on HTTP middleware alone.

## Event status manual change

- There is **no** dedicated Event status mutation API (`events.py` is GET-only).
- Status transitions happen inside pipelines; manual pipeline runs are audited via `pipeline.manual_run` (STARTED → SUCCESS|FAILED).
- HTTP middleware records `http.*` request-level events for all `/api/v1/**` mutating methods (POST/PUT/PATCH/DELETE), sharing the same `X-Correlation-ID`.

## Dual-write model

| Level | Action pattern | Meaning |
|-------|----------------|---------|
| request | `http.{method}` | Transport outcome (`status_code`); `detail.event_level=request` |
| business | `config.update`, `pipeline.manual_run`, `disposition.*`, … | Domain outcome; `detail.event_level=business` |

Same `correlation_id` links both. Do not treat `http.*` result as the business result (e.g. HTTP 200 with business `started` if finalize failed).

## Pipeline audit lifecycle

1. Persist `result=started` **before** pipeline side effects (fail-closed → 503, pipeline not started).
2. Run pipeline once; never re-run because audit finalize failed.
3. Update same row to `success` / `failure`; if update fails, leave `started` + CRITICAL log.
