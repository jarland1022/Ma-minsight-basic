#!/usr/bin/env python3
"""CI gate: forbid bare third-party HTTP clients outside approved modules (P0-06 / R-B).

Third-party data egress must go through app.privacy.egress_gateway.EgressGateway.
Customer-infra Wazuh Indexer pull remains an explicit minimal exception.

Does NOT claim coverage of opaque SDK-internal networking.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_APP_ROOT = Path(__file__).resolve().parents[1] / "app"

# Only these relative paths (under app/) may construct outbound HTTP clients.
ALLOW_DIRECT_HTTP = frozenset(
    {
        "privacy/egress_gateway.py",
        # Customer-infra ingress (Wazuh Indexer pull) — not third-party model egress
        "ingestion/adapters/wazuh/client.py",
    }
)

# Client construction / call patterns (line-oriented; comments skipped).
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("httpx.AsyncClient", re.compile(r"\bhttpx\.AsyncClient\s*\(")),
    ("httpx.Client", re.compile(r"\bhttpx\.Client\s*\(")),
    # Module-level conveniences also open outbound sockets (same bypass class as Client).
    (
        "httpx.request",
        re.compile(
            r"\bhttpx\.(get|post|put|patch|delete|request|head|options|stream)\s*\("
        ),
    ),
    (
        "requests",
        re.compile(r"\brequests\.(get|post|put|patch|delete|request|head|options|Session)\s*\("),
    ),
    ("aiohttp.ClientSession", re.compile(r"\baiohttp\.ClientSession\s*\(")),
    (
        "urllib.request",
        re.compile(
            r"\burllib\.request\.(urlopen|Request|urlretrieve|build_opener|FancyURLopener)\s*\("
        ),
    ),
    (
        "http.client",
        re.compile(r"\bhttp\.client\.(HTTPConnection|HTTPSConnection)\s*\("),
    ),
]


def find_violations(app_root: Path, *, allow: frozenset[str] = ALLOW_DIRECT_HTTP) -> list[str]:
    """Return human-readable violation lines for files under app_root."""
    violations: list[str] = []
    if not app_root.is_dir():
        raise FileNotFoundError(f"app root not found: {app_root}")

    for path in sorted(app_root.rglob("*.py")):
        rel = path.relative_to(app_root).as_posix()
        if rel in allow:
            continue
        # No blanket privacy/ exclusion — only egress_gateway.py is allowlisted.
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for _label, pat in PATTERNS:
                if pat.search(line):
                    violations.append(f"{rel}:{i}: {stripped}")
                    break
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P0-06 egress bypass static gate")
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_APP_ROOT,
        help="Application package root to scan (default: repo app/)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        violations = find_violations(root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if violations:
        print("P0-06 egress bypass check FAILED — bare HTTP clients outside allowlist:")
        for v in violations:
            print(f"  {v}")
        print(
            "\nRoute third-party egress through app.privacy.egress_gateway.EgressGateway, "
            "or add a documented minimal exception to scripts/check_egress_bypass.py "
            "ALLOW_DIRECT_HTTP (do not widen casually)."
        )
        print(f"Allowlist: {', '.join(sorted(ALLOW_DIRECT_HTTP))}")
        return 1
    print(f"P0-06 egress bypass check PASS (scanned {root})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
