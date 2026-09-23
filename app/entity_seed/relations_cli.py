"""CLI: import entity_relations from JSONL."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from app.db.session import async_session_factory
from app.entity_seed.relation_import import import_relations_jsonl

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def _run(args: argparse.Namespace) -> int:
    path = Path(args.file).expanduser().resolve()
    async with async_session_factory() as session:
        result = await import_relations_jsonl(session, path, dry_run=args.dry_run)
    print(
        json.dumps(
            {
                "file": str(path),
                "dry_run": args.dry_run,
                "lines_read": result.lines_read,
                "relations_upserted": result.relations_upserted,
                "updated_existing": result.updated_existing,
                "errors": result.errors,
            },
            ensure_ascii=False,
        )
    )
    return 0 if not result.errors else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import entity_relations from JSONL (one edge per line)"
    )
    parser.add_argument("--file", required=True, help="Path to relations.jsonl")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate file only; do not write to database",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
