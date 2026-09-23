#!/usr/bin/env bash
# Generate self-signed TLS cert for ECS-A HTTPS (IP or domain access).
# Browsers will warn — use for dev / internal IP access, or until Certbot is configured.
#
# Usage:
#   ./deploy/scripts/gen-self-signed-certs.sh 120.79.165.121
#   ./deploy/scripts/gen-self-signed-certs.sh ma-minsight.example.com
#   ./deploy/scripts/gen-self-signed-certs.sh 120.79.165.121 ma-minsight.example.com
set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

CERT_DIR="deploy/nginx/certs"
DAYS="${CERT_DAYS:-825}"
PRIMARY="${1:-}"

if [[ -z "$PRIMARY" ]]; then
  echo "Usage: $0 <public-ip-or-domain> [extra-domain-or-ip ...]"
  echo "Example: $0 120.79.165.121"
  exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: openssl not found. Install: yum install -y openssl  OR  apt install -y openssl"
  exit 1
fi

mkdir -p "$CERT_DIR"

# Build subjectAltName list (IP vs DNS).
SAN_PARTS=()
CN="$PRIMARY"
for item in "$@"; do
  if [[ "$item" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    SAN_PARTS+=("IP:${item}")
  else
    SAN_PARTS+=("DNS:${item}")
  fi
done
SAN=$(IFS=,; echo "${SAN_PARTS[*]}")

OPENSSL_CNF="$(mktemp)"
trap 'rm -f "$OPENSSL_CNF"' EXIT

cat >"$OPENSSL_CNF" <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3

[dn]
CN = ${CN}

[v3]
subjectAltName = ${SAN}
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
EOF

echo "Generating self-signed cert (${DAYS} days) for: ${SAN}"
openssl req -x509 -nodes -days "$DAYS" -newkey rsa:2048 \
  -keyout "${CERT_DIR}/privkey.pem" \
  -out "${CERT_DIR}/fullchain.pem" \
  -config "$OPENSSL_CNF"

chmod 600 "${CERT_DIR}/privkey.pem"
chmod 644 "${CERT_DIR}/fullchain.pem"

echo "Created:"
echo "  ${CERT_DIR}/fullchain.pem"
echo "  ${CERT_DIR}/privkey.pem"
echo ""
echo "Next: ./deploy/scripts/up-ecs-a.sh"
echo "Browser will show a security warning — accept for internal use, or replace with Certbot later."
