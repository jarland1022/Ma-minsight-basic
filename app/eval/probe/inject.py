"""Inject synthetic health-check alerts."""

from __future__ import annotations

from app.core.datetime_utils import as_naive_utc, utc_now
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AlertStatus
from app.eval.probe.guard import HEALTH_PROBE_KEY
from app.ingestion.adapters.wazuh.mapper import map_wazuh_alert
from app.models.cache_eval import HealthCheckScenario
from app.models.ingestion import Alert, DataSource

HEALTH_PROBE_SOURCE_NAME = "health_probe"


class ProbeInjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_probe_source(self) -> DataSource:
        result = await self.session.execute(
            select(DataSource).where(DataSource.name == HEALTH_PROBE_SOURCE_NAME)
        )
        source = result.scalar_one_or_none()
        if source is None:
            raise RuntimeError(
                f"DataSource '{HEALTH_PROBE_SOURCE_NAME}' not found; run alembic upgrade head"
            )
        return source

    async def inject(self, scenario: HealthCheckScenario) -> Alert:
        source = await self.get_probe_source()
        raw = dict(scenario.inject_payload)
        normalized = map_wazuh_alert(
            raw,
            data_source_id=source.id,
            data_source_name=source.name,
        )
        suffix = uuid4().hex[:8]
        source_alert_id = f"healthcheck-{scenario.name}-{suffix}"
        now = utc_now()
        occurred_at = as_naive_utc(normalized.occurred_at)

        fields = dict(normalized.normalized_fields)
        fields[HEALTH_PROBE_KEY] = True
        fields["health_check_scenario"] = scenario.name

        alert = Alert(
            data_source_id=source.id,
            source_alert_id=source_alert_id,
            fingerprint=f"probe-{suffix}-{normalized.fingerprint[:48]}",
            rule_id=normalized.rule_id,
            rule_name=normalized.rule_name,
            severity=normalized.severity,
            severity_raw=normalized.severity_raw,
            occurred_at=occurred_at,
            ingested_at=now,
            src_ip=normalized.src_ip,
            dst_ip=normalized.dst_ip,
            src_port=normalized.src_port,
            dst_port=normalized.dst_port,
            user_name=normalized.user_name,
            host_name=normalized.host_name,
            process_name=normalized.process_name,
            process_cmdline=normalized.process_cmdline,
            file_hash=normalized.file_hash,
            alert_category=normalized.alert_category,
            normalized_fields=fields,
            raw_data=normalized.raw_data,
            status=AlertStatus.NEW,
        )
        self.session.add(alert)
        await self.session.flush()
        return alert


async def get_probe_source(session: AsyncSession) -> DataSource:
    return await ProbeInjectService(session).get_probe_source()
