from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.db.session import engine


async def main() -> None:
    async with engine.connect() as c:
        print("ok", (await c.execute(text("select current_user, current_database()"))).first())
        rows = await c.execute(
            text(
                "select column_name from information_schema.columns "
                "where table_name='audit_logs' order by 1"
            )
        )
        print("cols", [r[0] for r in rows])
        ver = await c.execute(text("select version_num from alembic_version"))
        print("alembic", ver.scalar())


if __name__ == "__main__":
    asyncio.run(main())
