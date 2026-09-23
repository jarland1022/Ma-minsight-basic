"""Import entity_relations from JSONL (one relation per line)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import EntityType
from app.models.entity import EntityRelation

logger = logging.getLogger(__name__)

ENTITY_TYPE_MAP = {
    "ip": EntityType.IP,
    "host": EntityType.HOST,
    "user": EntityType.USER,
    "domain": EntityType.DOMAIN,
}

REQUIRED_FIELDS = (
    "from_entity_type",
    "from_entity_key",
    "to_entity_type",
    "to_entity_key",
    "relation_type",
)


@dataclass
class RelationImportResult:
    lines_read: int = 0
    relations_upserted: int = 0
    updated_existing: int = 0
    errors: list[str] = field(default_factory=list)


def _parse_entity_type(raw: str) -> EntityType:
    key = str(raw).strip().lower()
    if key not in ENTITY_TYPE_MAP:
        raise ValueError(f"invalid entity_type: {raw}")
    return ENTITY_TYPE_MAP[key]


def _parse_datetime(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def parse_relation_record(data: dict[str, Any], *, line_no: int) -> dict[str, Any]:
    missing = [f for f in REQUIRED_FIELDS if not str(data.get(f) or "").strip()]
    if missing:
        raise ValueError(f"line {line_no}: missing fields {missing}")

    confidence = float(data.get("confidence", 1.0))
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f"line {line_no}: confidence must be 0-1")

    metadata = data.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError(f"line {line_no}: metadata must be object")

    return {
        "from_entity_type": _parse_entity_type(data["from_entity_type"]),
        "from_entity_key": str(data["from_entity_key"]).strip(),
        "to_entity_type": _parse_entity_type(data["to_entity_type"]),
        "to_entity_key": str(data["to_entity_key"]).strip(),
        "relation_type": str(data["relation_type"]).strip(),
        "confidence": confidence,
        "source": str(data.get("source") or "import").strip()[:64],
        "metadata": metadata,
        "valid_from": _parse_datetime(data.get("valid_from")),
        "valid_until": _parse_datetime(data.get("valid_until")),
    }


async def upsert_entity_relation(session: AsyncSession, record: dict[str, Any]) -> bool:
    """Insert or update one relation edge. Returns True if a new row was created."""
    row = await session.execute(
        select(EntityRelation).where(
            EntityRelation.from_entity_type == record["from_entity_type"],
            EntityRelation.from_entity_key == record["from_entity_key"],
            EntityRelation.to_entity_type == record["to_entity_type"],
            EntityRelation.to_entity_key == record["to_entity_key"],
            EntityRelation.relation_type == record["relation_type"],
        )
    )
    rel = row.scalar_one_or_none()
    if rel is None:
        session.add(
            EntityRelation(
                from_entity_type=record["from_entity_type"],
                from_entity_key=record["from_entity_key"],
                to_entity_type=record["to_entity_type"],
                to_entity_key=record["to_entity_key"],
                relation_type=record["relation_type"],
                confidence=record["confidence"],
                source=record["source"],
                metadata_=record["metadata"],
                valid_from=record.get("valid_from"),
                valid_until=record.get("valid_until"),
            )
        )
        return True

    rel.confidence = record["confidence"]
    rel.source = record["source"]
    rel.metadata_ = record["metadata"]
    rel.valid_from = record.get("valid_from")
    rel.valid_until = record.get("valid_until")
    return False


async def import_relations_jsonl(
    session: AsyncSession,
    path: Path,
    *,
    dry_run: bool = False,
) -> RelationImportResult:
    result = RelationImportResult()
    if not path.is_file():
        result.errors.append(f"file not found: {path}")
        return result

    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        result.lines_read += 1
        try:
            data = json.loads(line)
            if not isinstance(data, dict):
                raise ValueError("each line must be a JSON object")
            record = parse_relation_record(data, line_no=line_no)
            if dry_run:
                result.relations_upserted += 1
                continue
            created = await upsert_entity_relation(session, record)
            result.relations_upserted += 1
            if not created:
                result.updated_existing += 1
        except Exception as exc:
            msg = str(exc)
            result.errors.append(msg)
            logger.warning("Relation import line %s failed: %s", line_no, msg)

    if not dry_run and result.relations_upserted and not result.errors:
        await session.commit()
    elif not dry_run and result.errors:
        await session.rollback()
    return result
