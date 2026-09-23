"""CLI for ingestion operations."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid

from sqlalchemy import select

from app.db.session import async_session_factory
from app.ingestion.services.ingest_service import IngestService
from app.models.ingestion import DataSource

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def _pull(source_ref: str, max_batches: int, no_lock: bool) -> int:
    async with async_session_factory() as session:
        query = select(DataSource)
        if _is_uuid(source_ref):
            query = query.where(DataSource.id == uuid.UUID(source_ref))
        else:
            query = query.where(DataSource.name == source_ref)

        result = await session.execute(query)
        source = result.scalar_one_or_none()
        if source is None:
            logger.error("DataSource not found: %s", source_ref)
            return 1

        service = IngestService(session)
        run_result = await service.run_for_source(
            source.id,
            max_batches=max_batches,
            use_lock=not no_lock,
        )
        if run_result.skipped_lock:
            logger.warning("Skipped: ingest lock held by another worker")
            return 2
        logger.info(
            "Pull complete source=%s inserted=%s duplicates=%s batches=%s",
            source.name,
            run_result.total_inserted,
            run_result.total_duplicates,
            len(run_result.batches),
        )
    return 0


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MA-MinSight ingestion CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    pull_parser = sub.add_parser("pull", help="Pull alerts for a data source")
    pull_parser.add_argument("--source", required=True, help="Data source name or UUID")
    pull_parser.add_argument("--max-batches", type=int, default=10)
    pull_parser.add_argument("--no-lock", action="store_true", help="Skip Redis distributed lock")

    args = parser.parse_args(argv)
    if args.command == "pull":
        return asyncio.run(_pull(args.source, args.max_batches, args.no_lock))
    return 1


if __name__ == "__main__":
    sys.exit(main())
