#!/usr/bin/env bash
# Post-deploy smoke checks (run on ECS host after compose up).
set -euo pipefail

BASE_URL="${SMOKE_BASE_URL:-http://127.0.0.1:${HTTP_PORT:-80}}"
API_KEY="${API_KEY:-}"

echo "==> GET $BASE_URL/health"
curl -fsS "$BASE_URL/health" | grep -q '"status":"ok"' && echo "OK: liveness"

echo "==> GET $BASE_URL/health/ready"
curl -fsS "$BASE_URL/health/ready" | grep -q '"status":"ready"' && echo "OK: readiness"

if [ -n "$API_KEY" ]; then
  echo "==> POST $BASE_URL/api/v1/health-checks/run (API key)"
  curl -fsS -X POST "$BASE_URL/api/v1/health-checks/run" \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" | grep -q '"total"' && echo "OK: health-check run"
else
  echo "SKIP: health-check run (set API_KEY env to enable)"
fi

echo "All smoke checks passed."
