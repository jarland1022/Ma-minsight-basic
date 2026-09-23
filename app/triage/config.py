"""Triage configuration loaded from system_config with defaults."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_config import get_config_bool, get_config_float, get_config_int, get_config_value
from app.triage.scoring.category_risk import DEFAULT_CATEGORY_RISK


@dataclass
class TriageConfig:
    dedup_window_minutes: int = 60
    deep_review_threshold: float = 70.0
    low_risk_threshold: float = 30.0
    uncertain_band_low: float = 30.0
    uncertain_band_high: float = 70.0
    sample_audit_rate: float = 0.01
    llm_assist_enabled: bool = False
    llm_weight: float = 0.15
    llm_assist_route_filter: list[str] = field(default_factory=lambda: ["queue_uncertain"])
    llm_assist_max_per_run: int = 20
    llm_assist_calls_this_run: int = 0
    profile_hint_cap: float = 20.0
    profile_hint_score_discount_cap: float = 6.0
    category_risk: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_CATEGORY_RISK))
    batch_size: int = 500


async def load_triage_config(session: AsyncSession) -> TriageConfig:
    category_override = await get_config_value(session, "triage.category_risk", None)
    category_risk = dict(DEFAULT_CATEGORY_RISK)
    if isinstance(category_override, dict):
        weights = category_override.get("weights")
        if isinstance(weights, dict):
            category_risk.update({str(k): float(v) for k, v in weights.items()})

    llm_route_raw = await get_config_value(session, "triage.llm_assist_route_filter", ["queue_uncertain"])
    if isinstance(llm_route_raw, dict) and "value" in llm_route_raw:
        llm_route_filter = [str(v) for v in llm_route_raw["value"]]
    elif isinstance(llm_route_raw, list):
        llm_route_filter = [str(v) for v in llm_route_raw]
    else:
        llm_route_filter = ["queue_uncertain"]

    return TriageConfig(
        dedup_window_minutes=await get_config_int(session, "triage.dedup_window_minutes", 60),
        deep_review_threshold=await get_config_float(session, "triage.deep_review_threshold", 70.0),
        low_risk_threshold=await get_config_float(session, "triage.low_risk_threshold", 30.0),
        uncertain_band_low=await get_config_float(session, "triage.uncertain_band_low", 30.0),
        uncertain_band_high=await get_config_float(session, "triage.uncertain_band_high", 70.0),
        sample_audit_rate=await get_config_float(session, "triage.sample_audit_rate", 0.01),
        llm_assist_enabled=await get_config_bool(session, "triage.llm_assist_enabled", False),
        llm_weight=await get_config_float(session, "triage.llm_weight", 0.15),
        llm_assist_route_filter=llm_route_filter,
        llm_assist_max_per_run=await get_config_int(session, "triage.llm_assist_max_per_run", 20),
        batch_size=await get_config_int(session, "triage.batch_size", 500),
        category_risk=category_risk,
    )


async def ensure_triage_defaults(session: AsyncSession) -> None:
    from app.services.system_config import ensure_config_key

    defaults: list[tuple[str, dict[str, Any], str]] = [
        ("triage.dedup_window_minutes", {"value": 60}, "Dedup sliding window in minutes"),
        ("triage.deep_review_threshold", {"value": 70}, "Effective score threshold for deep review queue"),
        ("triage.low_risk_threshold", {"value": 30}, "Below this score alerts may be archived as low risk"),
        ("triage.uncertain_band_low", {"value": 30}, "Lower bound of uncertain score band"),
        ("triage.uncertain_band_high", {"value": 70}, "Upper bound of uncertain score band"),
        ("triage.sample_audit_rate", {"value": 0.01}, "Random audit rate for archived low-risk alerts"),
        ("triage.llm_assist_enabled", {"value": False}, "Enable optional LLM assist scoring in triage"),
        ("triage.llm_weight", {"value": 0.15}, "LLM weight in effective triage score"),
        ("triage.batch_size", {"value": 500}, "Max NEW alerts processed per triage run"),
        ("triage.poll_interval_minutes", {"value": 2}, "Interval between triage scheduler runs"),
        (
            "triage.category_risk",
            {"weights": DEFAULT_CATEGORY_RISK},
            "Static category risk weights for rule scoring",
        ),
    ]
    for key, value, description in defaults:
        await ensure_config_key(session, key, value, description)
