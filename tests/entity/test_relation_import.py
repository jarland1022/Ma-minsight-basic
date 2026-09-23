"""Entity relation JSONL import tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.enums import EntityType
from app.entity_seed.relation_import import import_relations_jsonl, parse_relation_record


def test_parse_relation_record() -> None:
    record = parse_relation_record(
        {
            "from_entity_type": "ip",
            "from_entity_key": "10.0.0.1",
            "to_entity_type": "host",
            "to_entity_key": "web-01",
            "relation_type": "connects_to",
            "confidence": 0.9,
        },
        line_no=1,
    )
    assert record["from_entity_type"] == EntityType.IP
    assert record["relation_type"] == "connects_to"


@pytest.mark.asyncio
async def test_import_dry_run(tmp_path: Path) -> None:
    sample = Path(__file__).resolve().parents[1] / "fixtures" / "entity_relations.sample.jsonl"
    session = AsyncMock()
    result = await import_relations_jsonl(session, sample, dry_run=True)
    assert result.lines_read == 2
    assert result.relations_upserted == 2
    assert not result.errors
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_import_upserts() -> None:
    from app.entity_seed.relation_import import upsert_entity_relation

    session = AsyncMock()
    profile_result = MagicMock()
    profile_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=profile_result)

    record = parse_relation_record(
        {
            "from_entity_type": "ip",
            "from_entity_key": "1.2.3.4",
            "to_entity_type": "host",
            "to_entity_key": "h1",
            "relation_type": "has_host",
        },
        line_no=1,
    )
    created = await upsert_entity_relation(session, record)
    assert created is True
    session.add.assert_called_once()
