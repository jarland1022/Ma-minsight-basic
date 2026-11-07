#!/usr/bin/env bash
# ECS-A: rebuild and start with HTTPS on host port 6443.
set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

ensure_certs() {
  if [[ -f deploy/nginx/certs/fullchain.pem && -f deploy/nginx/certs/privkey.pem ]]; then
    return 0
  fi
  echo "ERROR: missing TLS certs under deploy/nginx/certs/"
  echo "  expected: fullchain.pem, privkey.pem"
  echo ""
  echo "Option A — self-signed (IP access, browser will warn):"
  echo "  ./deploy/scripts/gen-self-signed-certs.sh <公网IP>"
  echo "  ./deploy/scripts/up-ecs-a.sh"
  echo ""
  echo "Option B — one-shot self-signed + start:"
  echo "  ./deploy/scripts/up-ecs-a.sh --self-signed <公网IP>"
  echo ""
  echo "Option C — Let's Encrypt (needs domain + DNS):"
  echo "  see deploy/scripts/gen-letsencrypt-certs.sh"
  return 1
}

if [[ "${1:-}" == "--self-signed" ]]; then
  shift
  if [[ $# -lt 1 ]]; then
    echo "Usage: $0 --self-signed <public-ip-or-domain> [extra-san ...]"
    exit 1
  fi
  bash "$ROOT/deploy/scripts/gen-self-signed-certs.sh" "$@"
  set --
fi

ensure_certs

export HTTP_PORT="${HTTP_PORT:-8080}"
exec docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.ecs-a.yml \
  up -d --build "$@"
