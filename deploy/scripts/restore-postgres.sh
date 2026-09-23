#!/usr/bin/env bash
# Restore PostgreSQL from a gzipped pg_dump. DESTRUCTIVE — stops app first.
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <backup.sql.gz>" >&2
  exit 1
fi

BACKUP="$1"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "Missing .env" >&2
  exit 1
fi

if [ ! -f "$BACKUP" ]; then
  echo "File not found: $BACKUP" >&2
  exit 1
fi

echo "Stopping app and nginx ..."
docker compose stop app nginx

echo "Restoring from $BACKUP ..."
gunzip -c "$BACKUP" | docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

echo "Starting stack ..."
docker compose up -d app nginx
echo "Restore complete."
