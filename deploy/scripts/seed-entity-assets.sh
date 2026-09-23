#!/usr/bin/env bash
# Seed entity_profiles + on_duty_knowledge (your web servers, firewall, waf, scanner IP).
# Usage:
#   ./deploy/scripts/seed-entity-assets.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if docker compose ps --status running app 2>/dev/null | grep -q app; then
  docker compose exec -T app ma-entity-seed
else
  python -m app.entity_seed.cli
fi
