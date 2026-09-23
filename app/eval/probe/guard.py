"""Health probe isolation guards."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion import Alert
from app.models.investigation import EventAlert

HEALTH_PROBE_KEY = "health_probe"


def is_probe_fields(normalized_fields: dict | None) -> bool:
    if not normalized_fields:
        return False
    return bool(normalized_fields.get(HEALTH_PROBE_KEY))


def is_probe_alert(alert: Alert) -> bool:
    return is_probe_fields(alert.normalized_fields)


async def event_is_probe(session: AsyncSession, event_id: UUID) -> bool:
    stmt = (
        select(Alert.id)
        .join(EventAlert, EventAlert.alert_id == Alert.id)
        .where(
            EventAlert.event_id == event_id,
            Alert.normalized_fields[HEALTH_PROBE_KEY].as_boolean().is_(True),
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


def probe_event_ids_subquery():
    """Event IDs linked to at least one health-probe alert."""
    return (
        select(EventAlert.event_id)
        .join(Alert, Alert.id == EventAlert.alert_id)
        .where(Alert.normalized_fields[HEALTH_PROBE_KEY].as_boolean().is_(True))
        .distinct()
    )
