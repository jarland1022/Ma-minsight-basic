#!/usr/bin/env bash
# Build site/index.html from landing.html + landing.env
# Usage:
#   cp landing.env.example landing.env && $EDITOR landing.env
#   ./publish_landing.sh
#   ./publish_landing.sh --push-gh-pages
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../../.." && pwd)"
ENV_FILE="$HERE/landing.env"
# Canonical source for Pages workflow is docs/marketing/landing.html
SRC="$HERE/../landing.html"
[[ -f "$SRC" ]] || SRC="$HERE/landing.html"
SITE_DIR="$REPO_ROOT/site"
OUT="$SITE_DIR/index.html"
PUSH=0

for arg in "$@"; do
  case "$arg" in
    --push-gh-pages) PUSH=1 ;;
  esac
done

if [[ ! -f "$SRC" ]]; then
  echo "Missing $SRC" >&2
  exit 1
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Create landing.env first:"
  echo "  cp \"$HERE/landing.env.example\" \"$ENV_FILE\""
  exit 1
fi

# shellcheck disable=SC1090
set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

html="$(cat "$SRC")"
for key in YOUR_WHATSAPP_URL YOUR_CALENDLY_URL YOUR_GITHUB_URL YOUR_EMAIL YOUR_COMPANY; do
  val="${!key-}"
  if [[ -z "$val" || "$val" == *YOUR_* || "$val" == *example.com* || "$val" == *XXXXXXXX* ]]; then
    echo "Warning: set a real value for $key in landing.env" >&2
  fi
  html="${html//$key/$val}"
done

mkdir -p "$SITE_DIR"
printf '%s' "$html" > "$OUT"
[[ -f "$SITE_DIR/CNAME.example" ]] || echo "www.example.com" > "$SITE_DIR/CNAME.example"

echo "Built: $OUT"
echo
echo "Next: see github-pages.md — or enable Actions Variables and run the workflow."
echo "Local force push: ./publish_landing.sh --push-gh-pages"
echo "Live URL (after deploy): https://jarland1022.github.io/Ma-minsight-basic/"

if [[ "$PUSH" -ne 1 ]]; then
  exit 0
fi

TMP="$(mktemp -d)"
cp "$OUT" "$TMP/index.html"
[[ -f "$SITE_DIR/CNAME" ]] && cp "$SITE_DIR/CNAME" "$TMP/CNAME"
cd "$TMP"
git init -b gh-pages
git add index.html
[[ -f CNAME ]] && git add CNAME
git -c user.email="pages@ma-minsight.local" -c user.name="MA-MinSight Pages" commit -m "landing: $(date -u +%Y-%m-%dT%H:%MZ)"
REMOTE="$(git -C "$REPO_ROOT" remote get-url origin)"
git remote add origin "$REMOTE"
git push -f origin gh-pages:gh-pages
cd "$REPO_ROOT"
rm -rf "$TMP"
echo "Pushed gh-pages. Settings → Pages → branch gh-pages / (root)"
