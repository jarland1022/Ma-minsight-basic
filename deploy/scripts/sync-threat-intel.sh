#!/usr/bin/env bash
# Sync recent alert IPs to threat_intel_entries via AbuseIPDB / GreyNoise.
# Usage (on ECS host, from compose project directory):
#   ./deploy/scripts/sync-threat-intel.sh
#   ./deploy/scripts/sync-threat-intel.sh --force
# Cron example:
#   0 2 * * * cd /data/minsight && ./deploy/scripts/sync-threat-intel.sh >> /var/log/minsight-ti-sync.log 2>&1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

EXTRA_ARGS=("$@")

if docker compose ps --status running app 2>/dev/null | grep -q app; then
  docker compose exec -T app ma-ti-sync "${EXTRA_ARGS[@]}"
else
  python -m app.threat_intel.cli "${EXTRA_ARGS[@]}"
fi
