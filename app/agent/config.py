"""Investigation agent configuration."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_config import get_config_bool, get_config_float, get_config_int, get_config_value


@dataclass
class InvestigationConfig:
    poll_interval_minutes: int = 3
    batch_size: int = 5
    max_steps: int = 15
    max_skill_calls: int = 20
    daily_event_budget: int = 200
    model_name: str = "deepseek-chat"
    reasoner_model_name: str = "deepseek-reasoner"
    reasoner_enabled: bool = False
    alert_prompt_limit: int = 20
    skill_max_retries: int = 2
    closure_enabled: bool = True
    min_evidence_closure_score: float = 0.6
    min_refutation_coverage_for_attack: float = 0.5
    max_closure_retries: int = 2
    require_refutation_attempt: bool = True
    min_refuting_hints_checked: int = 1
    supervisor_enabled: bool = True
    supervisor_block_on_fail: bool = False


async def load_investigation_config(session: AsyncSession) -> InvestigationConfig:
    model_raw = await get_config_value(session, "investigation.model_name", "deepseek-chat")
    if isinstance(model_raw, dict) and "value" in model_raw:
        model_name = str(model_raw["value"])
    elif isinstance(model_raw, str):
        model_name = model_raw
    else:
        model_name = "deepseek-chat"

    return InvestigationConfig(
        poll_interval_minutes=await get_config_int(session, "investigation.poll_interval_minutes", 3),
        batch_size=await get_config_int(session, "investigation.batch_size", 5),
        max_steps=await get_config_int(session, "investigation.max_steps", 15),
        max_skill_calls=await get_config_int(session, "investigation.max_skill_calls", 20),
        daily_event_budget=await get_config_int(session, "investigation.daily_event_budget", 200),
        model_name=model_name,
        reasoner_enabled=await get_config_bool(session, "investigation.reasoner_enabled", False),
        alert_prompt_limit=await get_config_int(session, "investigation.alert_prompt_limit", 20),
        closure_enabled=await get_config_bool(session, "investigation.closure_enabled", True),
        min_evidence_closure_score=await get_config_float(
            session, "investigation.min_evidence_closure_score", 0.6
        ),
        min_refutation_coverage_for_attack=await get_config_float(
            session, "investigation.min_refutation_coverage_for_attack", 0.5
        ),
        max_closure_retries=await get_config_int(session, "investigation.max_closure_retries", 2),
        require_refutation_attempt=await get_config_bool(
            session, "investigation.require_refutation_attempt", True
        ),
        min_refuting_hints_checked=await get_config_int(
            session, "investigation.min_refuting_hints_checked", 1
        ),
        supervisor_enabled=await get_config_bool(session, "investigation.supervisor_enabled", True),
        supervisor_block_on_fail=await get_config_bool(
            session, "investigation.supervisor_block_on_fail", False
        ),
    )


async def ensure_investigation_defaults(session: AsyncSession) -> None:
    from app.services.system_config import ensure_config_key

    defaults = [
        ("investigation.poll_interval_minutes", {"value": 3}, "Agent investigation scheduler interval"),
        ("investigation.batch_size", {"value": 5}, "Max events investigated per run"),
        ("investigation.max_steps", {"value": 15}, "Max ReAct steps per investigation"),
        ("investigation.max_skill_calls", {"value": 20}, "Max skill invocations per investigation"),
        ("investigation.daily_event_budget", {"value": 200}, "Daily deep investigation event budget"),
        ("investigation.model_name", {"value": "deepseek-chat"}, "Default LLM for investigations"),
        ("investigation.reasoner_enabled", {"value": False}, "Reserved: enable reasoner re-run"),
        ("investigation.alert_prompt_limit", {"value": 20}, "Max alerts injected into investigation prompt"),
    ]
    for key, value, description in defaults:
        await ensure_config_key(session, key, value, description)
