"""Backfill GeoIP fields for existing alerts."""

from __future__ import annotations

import argparse
import asyncio
import logging

from pathlib import Path

from sqlalchemy import select, update

from app.core.logging_config import configure_logging
from app.db.session import async_session_factory
from app.geoip.enrich import format_src_geo_label
from app.geoip.lookup import get_geo_lookup
from app.models.ingestion import Alert

logger = logging.getLogger(__name__)


def describe_geo_status() -> str:
    """Human-readable GeoLite2 readiness for operators."""
    lookup = get_geo_lookup()
    path_text = lookup.db_path or "(未设置 GEOLITE2_CITY_PATH)"
    lines = [
        f"GEOLITE2_CITY_PATH={path_text}",
        f"enabled={lookup.enabled}",
        f"ready={lookup.is_ready}",
    ]
    if not lookup.db_path:
        lines.append("请在 .env 中设置 GEOLITE2_CITY_PATH，并 force-recreate app 容器。")
        return "\n".join(lines)

    path = Path(lookup.db_path)
    if path.is_file():
        lines.append(f"文件大小: {path.stat().st_size} bytes")
        return "\n".join(lines)

    if path.exists() and path.is_dir():
        lines.append("错误：配置路径指向目录，不是 .mmdb 文件。")
    elif not path.exists():
        lines.append("错误：容器内不存在该文件。")

    parent = path.parent
    if parent.exists():
        names = sorted(item.name for item in parent.iterdir())
        lines.append(f"目录 {parent} 内容: {', '.join(names) if names else '(空)'}")
    else:
        lines.append(f"目录 {parent} 不存在，请检查 docker-compose 是否挂载 GeoLite2 文件。")

    lines.append(
        "宿主机请将 GeoLite2-City.mmdb 放到 ./data/geoip/，"
        "或在 .env 设置 GEOLITE2_HOST_PATH=/宿主机/完整路径/GeoLite2-City.mmdb 后执行："
    )
    lines.append("docker compose up -d --force-recreate app")
    return "\n".join(lines)


async def _run(*, limit: int, force: bool) -> int:
    lookup = get_geo_lookup()
    if not lookup.is_ready:
        raise SystemExit(describe_geo_status())

    updated = 0
    scanned = 0

    async with async_session_factory() as session:
        query = (
            select(Alert)
            .where(Alert.src_ip.isnot(None))
            .order_by(Alert.occurred_at.desc())
            .limit(limit)
        )
        if not force:
            query = query.where(Alert.normalized_fields["src_geo"].is_(None))

        result = await session.execute(query)
        alerts = result.scalars().all()

        for alert in alerts:
            scanned += 1
            src_ip = str(alert.src_ip)
            geo = lookup.lookup(src_ip)
            if not geo:
                continue

            fields = dict(alert.normalized_fields or {})
            if not force and fields.get("src_geo"):
                continue
            fields["src_geo"] = geo
            await session.execute(
                update(Alert)
                .where(Alert.id == alert.id)
                .values(normalized_fields=fields)
            )
            updated += 1

        await session.commit()

    logger.info("GeoIP backfill complete: scanned=%s updated=%s", scanned, updated)
    return updated


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Backfill src_geo for existing alerts")
    parser.add_argument("--limit", type=int, default=5000, help="Max alerts to scan")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-resolve GeoIP even when src_geo already exists",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only print GeoLite2 path/mount status and exit",
    )
    args = parser.parse_args()

    if args.check:
        print(describe_geo_status())
        lookup = get_geo_lookup()
        raise SystemExit(0 if lookup.is_ready else 1)

    lookup = get_geo_lookup()
    if not lookup.is_ready:
        raise SystemExit(describe_geo_status())
    if lookup.is_ready:
        sample = lookup.lookup("8.8.8.8")
        if sample:
            label = format_src_geo_label({"src_geo": sample})
            logger.info("GeoLite2 sample lookup 8.8.8.8 -> %s", label)
    else:
        raise SystemExit(describe_geo_status())

    asyncio.run(_run(limit=args.limit, force=args.force))


if __name__ == "__main__":
    main()
