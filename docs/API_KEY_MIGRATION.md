# Legacy API_KEY → Scoped API Key migration (P0-02)

## Status

- Env `API_KEY` is treated as **Legacy** while `LEGACY_API_KEY_ENABLED=true` (default during compatibility window).
- Legacy keys are **never** full Admin and **cannot** call high-risk routes (O-07 Proposed): system config, users/MFA admin, license import, API key CRUD, whitelist-suppression enable (when present).
- Final cutover date (**O-02**) is **Proposed (30 days)** until Product Owner confirms.

## Operator steps

1. **Create a scoped key** (JWT admin session required):

   ```http
   POST /api/v1/api-keys
   Authorization: Bearer <admin_jwt>
   Content-Type: application/json

   {
     "name": "automation-ingest",
     "scopes": ["ingestion:pull", "pipeline:run:triage", "events:read"],
     "expires_at": null
   }
   ```

   Store `api_key` from the response **once**. List/detail never return plaintext.

2. **Point automation** at `X-API-Key: msk_...` (new secret).

3. **Verify**:
   - Positive: allowed scoped routes succeed.
   - Negative: `PUT /api/v1/system/config` → 403 (JWT admin only).
   - Negative: revoked/expired key → 401.

4. **Disable legacy accept** without deleting host env files:

   ```bash
   LEGACY_API_KEY_ENABLED=false
   ```

5. **Rotate** secrets out of the env secret store after PO-approved deadline.

6. **Production after window**: keep `LEGACY_API_KEY_ENABLED=false`. Scoped keys + JWT only.

## Rollback

Re-enable `LEGACY_API_KEY_ENABLED=true` for emergency automation **without** restoring high-risk privileges on the legacy key.

## Allowed scopes

See `app/services/api_key_scopes.py` → `ALLOWED_SCOPES`. No scope elevates to Admin (`admin`, `*`, `role:admin`, … are rejected).
