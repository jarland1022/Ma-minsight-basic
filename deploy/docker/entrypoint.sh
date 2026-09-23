#!/bin/sh
set -eu

log() {
  echo "[entrypoint] $*"
}

wait_for_tcp() {
  host="$1"
  port="$2"
  label="$3"
  max="${4:-60}"
  i=0
  while [ "$i" -lt "$max" ]; do
    if python - <<PY
import socket
s = socket.socket()
s.settimeout(2)
try:
    s.connect(("${host}", int("${port}")))
finally:
    s.close()
PY
    then
      log "${label} is ready (${host}:${port})"
      return 0
    fi
    i=$((i + 1))
    sleep 2
  done
  log "ERROR: timeout waiting for ${label} at ${host}:${port}"
  return 1
}

# Parse host/port from URLs when compose overrides are used.
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"

wait_for_tcp "$DB_HOST" "$DB_PORT" "PostgreSQL"
wait_for_tcp "$REDIS_HOST" "$REDIS_PORT" "Redis"

log "Running database migrations..."
attempt=1
while [ "$attempt" -le 5 ]; do
  if alembic upgrade head; then
    log "Migrations complete."
    break
  fi
  log "Migration attempt ${attempt} failed, retrying..."
  attempt=$((attempt + 1))
  sleep 3
done

if [ "$attempt" -gt 5 ]; then
  log "ERROR: migrations failed after 5 attempts"
  exit 1
fi

log "Starting: $*"
exec "$@"
