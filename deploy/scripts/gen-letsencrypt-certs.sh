#!/usr/bin/env bash
# Obtain Let's Encrypt cert via Certbot (requires a domain pointing to this host).
#
# Prerequisites:
#   - Domain DNS A record → this server's public IP
#   - Port 80 reachable from the internet (temporarily stop nginx on host 80 if occupied)
#
# Usage:
#   export CERT_DOMAIN=ma-minsight.example.com
#   export CERT_EMAIL=admin@example.com
#   ./deploy/scripts/gen-letsencrypt-certs.sh
#
# Then copy/link certs for nginx:
#   deploy/nginx/certs/fullchain.pem
#   deploy/nginx/certs/privkey.pem
set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

DOMAIN="${CERT_DOMAIN:-}"
EMAIL="${CERT_EMAIL:-}"
CERT_DIR="${ROOT}/deploy/nginx/certs"
WEBROOT="${CERTBOT_WEBROOT:-/var/www/certbot}"

if [[ -z "$DOMAIN" || -z "$EMAIL" ]]; then
  echo "Set CERT_DOMAIN and CERT_EMAIL environment variables."
  echo "Example:"
  echo "  CERT_DOMAIN=ma-minsight.example.com CERT_EMAIL=you@corp.com $0"
  exit 1
fi

if ! command -v certbot >/dev/null 2>&1; then
  echo "Install certbot first, e.g.:"
  echo "  yum install -y certbot   # Alibaba Cloud Linux / CentOS"
  echo "  apt install -y certbot   # Ubuntu"
  exit 1
fi

sudo mkdir -p "$WEBROOT"
sudo certbot certonly --webroot -w "$WEBROOT" -d "$DOMAIN" --email "$EMAIL" --agree-tos --non-interactive

LE="/etc/letsencrypt/live/${DOMAIN}"
if [[ ! -f "${LE}/fullchain.pem" ]]; then
  echo "ERROR: certbot did not create ${LE}/fullchain.pem"
  exit 1
fi

mkdir -p "$CERT_DIR"
sudo cp "${LE}/fullchain.pem" "${CERT_DIR}/fullchain.pem"
sudo cp "${LE}/privkey.pem" "${CERT_DIR}/privkey.pem"
sudo chown "$(whoami)" "${CERT_DIR}/fullchain.pem" "${CERT_DIR}/privkey.pem"
chmod 644 "${CERT_DIR}/fullchain.pem"
chmod 600 "${CERT_DIR}/privkey.pem"

echo "Certs installed to ${CERT_DIR}/"
echo "Next: ./deploy/scripts/up-ecs-a.sh"
