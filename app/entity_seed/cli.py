"""CLI to seed default entity profiles (enum-safe, no raw SQL)."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from app.db.session import async_session_factory
from app.entity_seed.service import seed_entity_assets

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def _run(_args: argparse.Namespace) -> int:
    async with async_session_factory() as session:
        result = await seed_entity_assets(session)
    print(
        json.dumps(
            {
                "profiles_upserted": result.profiles_upserted,
                "on_duty_upserted": result.on_duty_upserted,
                "relations_upserted": result.relations_upserted,
                "errors": result.errors,
            },
            ensure_ascii=False,
        )
    )
    return 0 if not result.errors else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed entity_profiles and on_duty_knowledge")
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
