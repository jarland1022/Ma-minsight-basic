"""Simulate disposition impact without executing enforcement actions."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import InvestigationContext
from app.db.enums import DispositionSimulationApprovalStatus
from app.defense_assets.disposition.config import load_disposition_config
from app.defense_assets.disposition.simulator import ACTION_PARAM_KEYS, DispositionSimulator
from app.models.defense_assets import DispositionSimulation
from app.skills.base import Skill, SkillResult


class SimulateDispositionSkill(Skill):
    name = "simulate_disposition"
    description = (
        "Simulate the blast radius of a proposed disposition (block_ip / isolate_host / disable_user). "
        "Read-only: creates an approval draft, never executes enforcement. "
        "Use before recommending high-impact actions."
    )

    @classmethod
    def parameters_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ["block_ip", "isolate_host", "disable_user"],
                },
                "action_params": {
                    "type": "object",
                    "description": "block_ip→ip; isolate_host→host_name; disable_user→user_name",
                    "properties": {
                        "ip": {"type": "string"},
                        "host_name": {"type": "string"},
                        "user_name": {"type": "string"},
                    },
                },
            },
            "required": ["action_type", "action_params"],
        }

    async def execute(
        self,
        params: dict[str, Any],
        ctx: InvestigationContext,
        session: AsyncSession,
    ) -> SkillResult:
        config = await load_disposition_config(session)
        if not config.simulation_enabled:
            return SkillResult(
                success=False,
                summary="Disposition simulation is disabled (disposition.simulation_enabled=false).",
                error="disabled",
            )

        action_type = str(params.get("action_type", "")).lower().strip()
        if action_type not in config.allowed_action_types:
            return SkillResult(
                success=False,
                summary=f"Action type '{action_type}' is not allowed.",
                error="action_not_allowed",
            )

        action_params = params.get("action_params") or {}
        if not isinstance(action_params, dict):
            return SkillResult(success=False, summary="action_params must be an object.", error="invalid_params")

        param_key = ACTION_PARAM_KEYS.get(action_type)
        if param_key and not str(action_params.get(param_key) or "").strip():
            return SkillResult(
                success=False,
                summary=f"action_params.{param_key} is required for {action_type}.",
                error="missing_target",
            )

        try:
            result = await DispositionSimulator().simulate(
                session,
                action_type=action_type,
                action_params=action_params,
                mock_mode=config.mock_mode,
            )
        except ValueError as exc:
            return SkillResult(success=False, summary=str(exc), error="simulation_error")

        impact = dict(result.simulated_impact)
        impact["requires_approval"] = config.require_approval

        simulation = DispositionSimulation(
            investigation_id=ctx.investigation_id,
            action_type=result.action_type,
            action_params=result.action_params,
            simulated_impact=impact,
            approval_status=DispositionSimulationApprovalStatus.DRAFT,
        )
        session.add(simulation)
        await session.flush()

        approval_note = (
            "推演记录已保存为 draft，需在控制台审批；本系统不会自动执行处置。"
            if config.require_approval
            else "推演完成（未强制审批）。"
        )
        return SkillResult(
            success=True,
            summary=f"{result.summary} {approval_note}",
            data={
                "simulation_id": str(simulation.id),
                "action_type": result.action_type,
                "action_params": result.action_params,
                "simulated_impact": impact,
                "approval_status": simulation.approval_status.value,
            },
            evidence_ref=f"simulation:{simulation.id}",
        )
