"""CLI for syncing external threat intel into the local cache."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from app.db.session import async_session_factory
from app.threat_intel.sync_service import ThreatIntelSyncService

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def _run(args: argparse.Namespace) -> int:
    ips = [part.strip() for part in args.ip.split(",") if part.strip()] if args.ip else None
    async with async_session_factory() as session:
        result = await ThreatIntelSyncService(session).run(
            window_days=args.window_days,
            limit=args.limit,
            force=args.force,
            dry_run=args.dry_run,
            ips=ips,
        )

    payload = {
        "candidates": result.candidates,
        "skipped_private": result.skipped_private,
        "skipped_fresh": result.skipped_fresh,
        "synced": result.synced,
        "failed": result.failed,
        "errors": result.errors[:20],
    }
    print(json.dumps(payload, ensure_ascii=False))

    if result.errors and not result.synced:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync external threat intel into threat_intel_entries")
    parser.add_argument("--window-days", type=int, default=None, help="Look back N days in alerts for IPs")
    parser.add_argument("--limit", type=int, default=None, help="Max distinct IPs to process")
    parser.add_argument("--ip", help="Sync specific IP(s), comma-separated")
    parser.add_argument("--force", action="store_true", help="Refresh even when a fresh cache row exists")
    parser.add_argument("--dry-run", action="store_true", help="Lookup providers but do not write to DB")
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
