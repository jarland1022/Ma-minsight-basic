from __future__ import annotations

import asyncio
import os
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main() -> None:
    user = os.environ.get("POSTGRES_USER", "ai_sec")
    password = os.environ.get("POSTGRES_PASSWORD", "AiSec$2026#")
    db = os.environ.get("POSTGRES_DB", "ai_sec")
    url = f"postgresql+asyncpg://{user}:{quote_plus(password)}@127.0.0.1:5432/{db}"
    print("url", url)
    engine = create_async_engine(url)
    async with engine.connect() as c:
        print("ping", (await c.execute(text("select 1"))).scalar())
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
