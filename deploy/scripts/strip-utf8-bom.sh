#!/usr/bin/env bash
# Remove UTF-8 BOM from text files (fixes pip/tomllib TOMLDecodeError on Linux).
set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

fixed=0
while IFS= read -r -d '' f; do
  if head -c 3 "$f" | od -An -tx1 | grep -q 'ef bb bf'; then
    tail -c +4 "$f" > "${f}.tmp" && mv "${f}.tmp" "$f"
    echo "stripped BOM: $f"
    fixed=$((fixed + 1))
  fi
done < <(find . -type f \( \
  -name '*.toml' -o -name '*.md' -o -name '*.ini' -o -name '*.py' -o \
  -name '*.yml' -o -name '*.yaml' -o -name '*.sh' -o -name '*.conf' -o \
  -name '*.example' -o -name '*.tsx' -o -name '*.ts' -o -name '*.html' -o -name '*.json' \
  \) ! -path './.git/*' ! -path './node_modules/*' ! -path './web/node_modules/*' -print0)

echo "Done. Fixed $fixed file(s)."
