"""Evaluation / health-check configuration."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import InvestigationVerdict
from app.services.system_config import get_config_bool, get_config_int, get_config_value


@dataclass
class EvalConfig:
    regression_enabled: bool = True
    regression_use_real_llm_default: bool = False
    regression_cron: str | None = None
    health_check_enabled: bool = True
    health_check_cron: str | None = None
    health_check_agent_mock_verdict: InvestigationVerdict = InvestigationVerdict.LIKELY_FALSE_POSITIVE
    probe_retention_days: int = 7
    alert_webhook_url: str | None = None


async def load_eval_config(session: AsyncSession) -> EvalConfig:
    verdict_raw = await get_config_value(
        session,
        "eval.health_check_agent_mock_verdict",
        {"value": InvestigationVerdict.LIKELY_FALSE_POSITIVE.value},
    )
    if isinstance(verdict_raw, dict):
        verdict_raw = verdict_raw.get("value", InvestigationVerdict.LIKELY_FALSE_POSITIVE.value)
    webhook = await get_config_value(session, "eval.alert_webhook_url", None)
    if isinstance(webhook, dict):
        webhook = webhook.get("value")

    cron_reg = await get_config_value(session, "eval.regression_cron", None)
    if isinstance(cron_reg, dict):
        cron_reg = cron_reg.get("value")

    cron_hc = await get_config_value(session, "eval.health_check_cron", None)
    if isinstance(cron_hc, dict):
        cron_hc = cron_hc.get("value")

    return EvalConfig(
        regression_enabled=await get_config_bool(session, "eval.regression_enabled", True),
        regression_use_real_llm_default=await get_config_bool(
            session, "eval.regression_use_real_llm_default", False
        ),
        regression_cron=cron_reg if cron_reg else None,
        health_check_enabled=await get_config_bool(session, "eval.health_check_enabled", True),
        health_check_cron=cron_hc if cron_hc else None,
        health_check_agent_mock_verdict=InvestigationVerdict(str(verdict_raw)),
        probe_retention_days=await get_config_int(session, "eval.probe_retention_days", 7),
        alert_webhook_url=str(webhook) if webhook else None,
    )


async def ensure_eval_defaults(session: AsyncSession) -> None:
    from app.services.system_config import ensure_config_key

    defaults = [
        ("eval.regression_enabled", {"value": True}, "Enable regression test runner"),
        ("eval.regression_use_real_llm_default", {"value": False}, "Default use real LLM for regression"),
        ("eval.regression_cron", {"value": None}, "Cron for regression (null=disabled)"),
        ("eval.health_check_enabled", {"value": True}, "Enable health check runner"),
        ("eval.health_check_cron", {"value": None}, "Cron for health checks (null=disabled)"),
        (
            "eval.health_check_agent_mock_verdict",
            {"value": InvestigationVerdict.LIKELY_FALSE_POSITIVE.value},
            "Mock verdict for health-check agent stage",
        ),
        ("eval.probe_retention_days", {"value": 7}, "Days to retain probe alerts/events"),
        ("eval.alert_webhook_url", {"value": None}, "Optional webhook URL on eval failure"),
    ]
    for key, value, desc in defaults:
        await ensure_config_key(session, key, value, desc)
