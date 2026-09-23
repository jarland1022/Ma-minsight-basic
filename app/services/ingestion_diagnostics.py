"""Ingestion troubleshooting: connectivity, cursor, and lookback analysis."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.ingestion.adapters.bootstrap  # noqa: F401 — register adapters
from app.core.datetime_utils import as_naive_utc, utc_now
from app.geoip.lookup import get_geo_lookup
from app.ingestion.adapters.registry import AdapterRegistry
from app.ingestion.adapters.wazuh.client import WazuhIndexerClient
from app.ingestion.schemas.cursor import CursorState
from app.ingestion.schemas.wazuh_config import WazuhIndexerConfig
from app.models.ingestion import Alert, DataSource

logger = logging.getLogger(__name__)

CheckStatus = Literal["ok", "warn", "error", "info", "skip"]
OverallStatus = Literal["ok", "warn", "error"]


class DiagnosticCheck(BaseModel):
    id: str
    label: str
    status: CheckStatus
    message: str
    detail: str | None = None
    suggestion: str | None = None


class DataSourceStats(BaseModel):
    alerts_in_db: int = 0
    cursor_last_occurred_at: str | None = None
    cursor_total_ingested: int = 0
    last_successful_run_at: str | None = None
    initial_lookback_hours: int | None = None
    indexer_url: str | None = None
    indexer_latest_at: str | None = None
    indexer_total_alerts: int | None = None
    window_start: str | None = None
    window_match_count: int | None = None


class DataSourceDiagnostics(BaseModel):
    data_source_id: str
    name: str
    adapter_type: str
    is_active: bool
    overall_status: OverallStatus
    checks: list[DiagnosticCheck] = Field(default_factory=list)
    stats: DataSourceStats = Field(default_factory=DataSourceStats)
    actions_available: list[str] = Field(default_factory=list)


class IngestionDiagnosticsReport(BaseModel):
    generated_at: str
    overall_status: OverallStatus
    sources: list[DataSourceDiagnostics] = Field(default_factory=list)
    summary: str
    geolite2_ready: bool = False
    geolite2_path: str | None = None


class IngestionDiagnosticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(self) -> IngestionDiagnosticsReport:
        result = await self.session.execute(select(DataSource).order_by(DataSource.name))
        sources = result.scalars().all()

        reports: list[DataSourceDiagnostics] = []
        for source in sources:
            reports.append(await self._diagnose_source(source))

        overall = self._aggregate_status(reports)
        summary = self._build_summary(reports, overall)
        geo_lookup = get_geo_lookup()
        return IngestionDiagnosticsReport(
            generated_at=utc_now().isoformat(),
            overall_status=overall,
            sources=reports,
            summary=summary,
            geolite2_ready=geo_lookup.is_ready,
            geolite2_path=geo_lookup.db_path or None,
        )

    async def extend_lookback(
        self,
        data_source_id: UUID,
        *,
        lookback_hours: int = 168,
        reset_cursor: bool = True,
    ) -> DataSourceDiagnostics:
        source = await self._get_source(data_source_id)
        if source is None:
            raise ValueError("DataSource not found")
        if source.adapter_type != "wazuh":
            raise ValueError("仅 Wazuh 数据源支持调整回溯窗口")

        config = dict(source.config or {})
        config["initial_lookback_hours"] = lookback_hours
        source.config = config

        if reset_cursor:
            source.cursor_state = {
                "version": 1,
                "mode": "search_after",
                "last_occurred_at": None,
                "last_sort_values": None,
                "total_ingested": source.cursor_state.get("total_ingested", 0)
                if source.cursor_state
                else 0,
            }

        await self.session.commit()
        await self.session.refresh(source)
        return await self._diagnose_source(source)

    async def _diagnose_source(self, source: DataSource) -> DataSourceDiagnostics:
        checks: list[DiagnosticCheck] = []
        stats = await self._load_stats(source)
        actions: list[str] = []

        if not source.is_active:
            checks.append(
                DiagnosticCheck(
                    id="inactive",
                    label="数据源状态",
                    status="warn",
                    message="数据源已禁用",
                    suggestion="在 data_sources 表或部署配置中启用该数据源。",
                )
            )

        if source.adapter_type == "health_probe":
            checks.append(
                DiagnosticCheck(
                    id="health_probe",
                    label="探针数据源",
                    status="info",
                    message="health_probe 为链路自检专用，不会从外部拉取告警",
                    detail="入库显示 fetched=0 属于正常现象；请使用「链路探针」验证端到端流程。",
                )
            )
            return DataSourceDiagnostics(
                data_source_id=str(source.id),
                name=source.name,
                adapter_type=source.adapter_type,
                is_active=source.is_active,
                overall_status="ok" if source.is_active else "warn",
                checks=checks,
                stats=stats,
                actions_available=[],
            )

        if source.adapter_type not in AdapterRegistry.registered_types():
            checks.append(
                DiagnosticCheck(
                    id="unknown_adapter",
                    label="适配器",
                    status="error",
                    message=f"未知适配器类型：{source.adapter_type}",
                    suggestion="检查部署版本是否包含该适配器，或修正 adapter_type。",
                )
            )
            return self._build_report(source, checks, stats, actions)

        if source.adapter_type == "wazuh":
            wazuh_checks, wazuh_actions = await self._diagnose_wazuh(source, stats)
            checks.extend(wazuh_checks)
            actions.extend(wazuh_actions)

        return self._build_report(source, checks, stats, actions)

    async def _diagnose_wazuh(
        self,
        source: DataSource,
        stats: DataSourceStats,
    ) -> tuple[list[DiagnosticCheck], list[str]]:
        checks: list[DiagnosticCheck] = []
        actions: list[str] = []

        try:
            config = WazuhIndexerConfig.model_validate(source.config or {})
            stats.initial_lookback_hours = config.initial_lookback_hours
            stats.indexer_url = config.indexer_url
            config.resolve_credentials()
        except ValueError as exc:
            checks.append(
                DiagnosticCheck(
                    id="credentials",
                    label="Indexer 凭据",
                    status="error",
                    message=str(exc),
                    suggestion="在 .env 或容器环境中设置 WAZUH_INDEXER_USER 与 WAZUH_INDEXER_PASSWORD。",
                )
            )
            return checks, actions

        cursor = CursorState.model_validate(source.cursor_state or {})
        try:
            async with WazuhIndexerClient(config) as client:
                probe = await client.probe(cursor)
        except Exception as exc:
            logger.exception("Wazuh probe failed for source=%s", source.name)
            checks.append(
                DiagnosticCheck(
                    id="connection",
                    label="Indexer 连接",
                    status="error",
                    message=f"探测失败：{exc}",
                    suggestion="检查 indexer_url、网络连通性与 TLS 配置（verify_tls / ca_cert_path）。",
                )
            )
            return checks, actions

        if probe.window_start:
            stats.window_start = probe.window_start.isoformat()

        if not probe.connected:
            checks.append(
                DiagnosticCheck(
                    id="connection",
                    label="Indexer 连接",
                    status="error",
                    message=probe.error or "无法连接 Wazuh Indexer",
                    detail=f"目标地址：{config.indexer_url}",
                    suggestion="确认 ECS-B Indexer 可达、端口开放，且账号密码正确。",
                )
            )
            return checks, actions

        checks.append(
            DiagnosticCheck(
                id="connection",
                label="Indexer 连接",
                status="ok",
                message=f"连接正常（HTTP {probe.http_status}）",
                detail=f"索引：{config.index_pattern}，地址：{config.indexer_url}",
            )
        )

        if probe.total_alerts is not None:
            stats.indexer_total_alerts = probe.total_alerts
        if probe.latest_timestamp:
            stats.indexer_latest_at = probe.latest_timestamp.isoformat()
        if probe.window_match_count is not None:
            stats.window_match_count = probe.window_match_count

        if probe.total_alerts == 0:
            checks.append(
                DiagnosticCheck(
                    id="indexer_data",
                    label="Indexer 告警",
                    status="warn",
                    message="Indexer 中暂无告警数据",
                    suggestion="在 Wazuh/Suricata 侧确认告警是否写入 Indexer。",
                )
            )
            return checks, actions

        lookback = config.initial_lookback_hours
        now = utc_now()
        window_start = probe.window_start or (now - timedelta(hours=lookback))

        if cursor.last_occurred_at is None:
            checks.append(
                DiagnosticCheck(
                    id="cursor",
                    label="入库游标",
                    status="info",
                    message="游标为空，将按初始回溯窗口拉取",
                    detail=f"回溯 {lookback} 小时，自 {window_start.isoformat()} 起",
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    id="cursor",
                    label="入库游标",
                    status="ok",
                    message=f"已追平至 {cursor.last_occurred_at.isoformat()}",
                    detail=f"游标累计入库 {cursor.total_ingested} 条（游标计数，非 DB 总数）",
                )
            )

        window_count = probe.window_match_count or 0
        latest = probe.latest_timestamp

        if window_count == 0 and latest and latest < window_start:
            checks.append(
                DiagnosticCheck(
                    id="lookback_gap",
                    label="回溯窗口",
                    status="warn",
                    message=(
                        f"当前回溯 {lookback} 小时内无告警，"
                        f"Indexer 最新告警为 {latest.isoformat()}"
                    ),
                    detail=(
                        "游标重置后默认只查最近 "
                        f"{lookback} 小时；较旧的告警不会进入增量查询。"
                    ),
                    suggestion="点击下方「扩大回溯并重新拉取」可补拉最多 7 天内的历史告警。",
                )
            )
            actions.append("extend_lookback")
        elif window_count == 0 and latest and cursor.last_occurred_at:
            lag = as_naive_utc(latest) - as_naive_utc(cursor.last_occurred_at)
            if abs(lag.total_seconds()) < 60:
                checks.append(
                    DiagnosticCheck(
                        id="caught_up",
                        label="增量状态",
                        status="ok",
                        message="已追平 Indexer 最新告警，暂无新数据",
                        detail=f"Indexer 最新：{latest.isoformat()}；库内 {stats.alerts_in_db} 条",
                        suggestion="等待 Wazuh 产生新告警后会自动入库；也可手动点击「告警入库」。",
                    )
                )
            else:
                checks.append(
                    DiagnosticCheck(
                        id="caught_up",
                        label="增量状态",
                        status="warn",
                        message="当前增量窗口内无匹配告警",
                        detail=f"Indexer 最新：{latest.isoformat()}",
                        suggestion="若刚重置游标，请尝试扩大回溯窗口。",
                    )
                )
                actions.append("extend_lookback")
        elif window_count == 0:
            checks.append(
                DiagnosticCheck(
                    id="empty_window",
                    label="增量窗口",
                    status="warn",
                    message="当前查询条件下 Indexer 返回 0 条",
                    suggestion="检查 index_pattern 是否正确，或扩大回溯窗口。",
                )
            )
            actions.append("extend_lookback")
        else:
            dup_hint = ""
            if stats.alerts_in_db > 0 and window_count > 0:
                dup_hint = "（若库内已有相同告警，入库时会计为重复）"
            checks.append(
                DiagnosticCheck(
                    id="pending_pull",
                    label="待拉取告警",
                    status="ok",
                    message=f"增量窗口内约 {window_count} 条告警可拉取{dup_hint}",
                    suggestion="点击上方「告警入库」或等待定时任务自动同步。",
                )
            )

        if stats.alerts_in_db == 0 and window_count > 0:
            checks.append(
                DiagnosticCheck(
                    id="db_empty",
                    label="本地告警库",
                    status="warn",
                    message="库内尚无告警，但 Indexer 有数据可拉",
                    suggestion="执行「告警入库」写入 alerts 表。",
                )
            )

        return checks, actions

    async def _load_stats(self, source: DataSource) -> DataSourceStats:
        count_result = await self.session.execute(
            select(func.count()).select_from(Alert).where(Alert.data_source_id == source.id)
        )
        alerts_in_db = int(count_result.scalar_one())

        cursor = source.cursor_state or {}
        last_at = cursor.get("last_occurred_at")
        last_run = cursor.get("last_successful_run_at")

        return DataSourceStats(
            alerts_in_db=alerts_in_db,
            cursor_last_occurred_at=str(last_at) if last_at else None,
            cursor_total_ingested=int(cursor.get("total_ingested", 0)),
            last_successful_run_at=str(last_run) if last_run else None,
        )

    def _build_report(
        self,
        source: DataSource,
        checks: list[DiagnosticCheck],
        stats: DataSourceStats,
        actions: list[str],
    ) -> DataSourceDiagnostics:
        return DataSourceDiagnostics(
            data_source_id=str(source.id),
            name=source.name,
            adapter_type=source.adapter_type,
            is_active=source.is_active,
            overall_status=self._status_from_checks(checks),
            checks=checks,
            stats=stats,
            actions_available=sorted(set(actions)),
        )

    @staticmethod
    def _status_from_checks(checks: list[DiagnosticCheck]) -> OverallStatus:
        if any(c.status == "error" for c in checks):
            return "error"
        if any(c.status == "warn" for c in checks):
            return "warn"
        return "ok"

    @staticmethod
    def _aggregate_status(reports: list[DataSourceDiagnostics]) -> OverallStatus:
        real = [r for r in reports if r.adapter_type != "health_probe"]
        if not real:
            return "ok"
        if any(r.overall_status == "error" for r in real):
            return "error"
        if any(r.overall_status == "warn" for r in real):
            return "warn"
        return "ok"

    @staticmethod
    def _build_summary(reports: list[DataSourceDiagnostics], overall: OverallStatus) -> str:
        wazuh = next((r for r in reports if r.adapter_type == "wazuh"), None)
        if wazuh is None:
            return "未配置 Wazuh 数据源。"
        if overall == "ok":
            pending = wazuh.stats.window_match_count or 0
            if pending > 0:
                return f"Wazuh 连接正常，约 {pending} 条告警待入库。"
            return "Wazuh 连接正常，已追平 Indexer，暂无新告警。"
        if overall == "error":
            err = next((c for c in wazuh.checks if c.status == "error"), None)
            return err.message if err else "Wazuh 数据源存在错误，请查看下方检查项。"
        warn = next((c for c in wazuh.checks if c.status == "warn"), None)
        return warn.message if warn else "Wazuh 数据源需关注，请查看下方检查项。"

    async def _get_source(self, data_source_id: UUID) -> DataSource | None:
        result = await self.session.execute(
            select(DataSource).where(DataSource.id == data_source_id)
        )
        return result.scalar_one_or_none()
