"""query_sample_enrichment skill tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.context import AlertBrief, EventBrief, InvestigationContext
from app.db.enums import IocType, ThreatIntelVerdict
from app.skills.query_sample_enrichment import QuerySampleEnrichmentSkill, _HASH_RE


def _ctx() -> InvestigationContext:
    now = datetime.now(UTC)
    return InvestigationContext(
        investigation_id=uuid.uuid4(),
        event=EventBrief(
            id=uuid.uuid4(),
            title="malware",
            primary_category="malware",
            queue_priority=1,
            risk_score=80,
            alert_count=1,
            first_alert_at=now,
            last_alert_at=now,
            aggregate_host_name="pc-1",
        ),
        alerts=[
            AlertBrief(
                id=uuid.uuid4(),
                occurred_at=now,
                rule_name="malware",
                severity=10,
                host_name="pc-1",
            )
        ],
    )


@pytest.mark.asyncio
async def test_sample_enrichment_from_alert_hash() -> None:
    skill = QuerySampleEnrichmentSkill()
    ctx = _ctx()
    digest = "a" * 64
    alert = SimpleNamespace(
        id=uuid.uuid4(),
        source_alert_id="wazuh-1",
        occurred_at=datetime.now(UTC),
        rule_name="Syscheck",
        file_hash=digest,
        process_name="installer.exe",
        host_name="pc-1",
    )
    intel = SimpleNamespace(
        source="abuseipdb",
        verdict=ThreatIntelVerdict.MALICIOUS,
        confidence=0.9,
        fetched_at=datetime.now(UTC),
        raw_response={},
    )

    session = MagicMock()
    alert_result = MagicMock()
    alert_result.scalars.return_value.all.return_value = [alert]
    intel_result = MagicMock()
    intel_result.scalars.return_value.all.return_value = [intel]
    session.execute = AsyncMock(side_effect=[alert_result, intel_result])

    out = await skill.execute({}, ctx, session)
    assert out.success
    assert out.data["has_hash"] is True
    assert out.data["sandbox_available"] is False
    assert out.data["samples"][0]["file_hash"] == digest
    assert out.data["samples"][0]["intel"]["verdict"] == "malicious"
    assert "verification" in out.data


@pytest.mark.asyncio
async def test_sample_enrichment_empty_when_no_hash() -> None:
    skill = QuerySampleEnrichmentSkill()
    ctx = _ctx()
    session = MagicMock()
    empty = MagicMock()
    empty.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=empty)

    out = await skill.execute({}, ctx, session)
    assert out.success
    assert out.data["sample_count"] == 0
    assert "do not invent" in out.summary.lower() or "unavailable" in out.summary.lower()


def test_hash_regex() -> None:
    assert _HASH_RE.match("a" * 32)
    assert _HASH_RE.match("b" * 40)
    assert _HASH_RE.match("c" * 64)
    assert not _HASH_RE.match("short")
