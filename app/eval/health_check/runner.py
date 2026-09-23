"""Health-check scenario execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from app.core.datetime_utils import utc_now
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import ActorType, HealthCheckStage
from app.eval.config import load_eval_config
from app.eval.evaluators.outcome_diff import diff_outcome
from app.eval.health_check.stage_runner import collect_actual_state, run_to_stage
from app.eval.lock import health_check_lock
from app.eval.notifications import notify_eval_failure
from app.eval.probe.inject import ProbeInjectService
from app.models.cache_eval import HealthCheckRun, HealthCheckScenario
from app.models.system import AuditLog

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckBatchResult:
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped_lock: bool = False
    run_ids: list[UUID] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class HealthCheckRunner:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(
        self,
        *,
        scenario_id: UUID | None = None,
        trigger: str = "manual",
        use_lock: bool = True,
    ) -> HealthCheckBatchResult:
        result = HealthCheckBatchResult()

        async def _execute() -> HealthCheckBatchResult:
            try:
                config = await load_eval_config(self.session)
            except ValueError as exc:
                result.errors.append(f"invalid eval config: {exc}")
                return result
            if not config.health_check_enabled:
                result.errors.append("health checks disabled")
                return result

            scenarios = await self._load_scenarios(scenario_id)
            if not scenarios:
                result.errors.append("no active health check scenarios")
                return result

            injector = ProbeInjectService(self.session)
            passed_count = 0
            for scenario in scenarios:
                try:
                    run_id, ok = await self._run_one(injector, scenario, trigger)
                    result.run_ids.append(run_id)
                    result.total += 1
                    if ok:
                        passed_count += 1
                except Exception as exc:
                    await self.session.rollback()
                    result.errors.append(f"{scenario.name}: {exc}")
                    logger.exception("Health check failed for %s", scenario.name)

            result.passed = passed_count
            result.failed = result.total - passed_count

            if result.failed:
                await notify_eval_failure(
                    self.session,
                    title="Health check failed",
                    detail=f"{result.failed}/{result.total} scenarios failed",
                )
            return result

        if use_lock:
            async with health_check_lock() as acquired:
                if not acquired:
                    result.skipped_lock = True
                    return result
                return await _execute()
        return await _execute()

    async def _load_scenarios(self, scenario_id: UUID | None) -> list[HealthCheckScenario]:
        stmt = select(HealthCheckScenario).where(HealthCheckScenario.is_active.is_(True))
        if scenario_id:
            stmt = stmt.where(HealthCheckScenario.id == scenario_id)
        stmt = stmt.order_by(HealthCheckScenario.name)
        return list((await self.session.execute(stmt)).scalars().all())

    async def _run_one(
        self,
        injector: ProbeInjectService,
        scenario: HealthCheckScenario,
        trigger: str,
    ) -> tuple[UUID, bool]:
        try:
            alert = await injector.inject(scenario)
            await self.session.commit()

            stage_results = await run_to_stage(
                self.session,
                alert.id,
                scenario.expected_stage,
            )
            actual = await collect_actual_state(self.session, alert.id)
            passed, mismatches = diff_outcome(scenario.expected_outcome, actual)

            run = HealthCheckRun(
                scenario_id=scenario.id,
                passed=passed,
                stage_results={
                    "trigger": trigger,
                    "stages": stage_results,
                    "actual": actual,
                    "mismatches": mismatches,
                },
                error_message=None if passed else str(mismatches),
                run_at=utc_now(),
            )
            self.session.add(run)
            self.session.add(
                AuditLog(
                    actor_type=ActorType.SYSTEM,
                    action="health_check.passed" if passed else "health_check.failed",
                    resource_type="health_check",
                    resource_id=str(scenario.id),
                    detail={"scenario": scenario.name, "passed": passed},
                )
            )
            await self.session.commit()
            await self.session.refresh(run)
            return run.id, passed
        except Exception:
            await self.session.rollback()
            raise

    async def latest_summary(self) -> dict | None:
        stmt = (
            select(HealthCheckRun)
            .order_by(HealthCheckRun.run_at.desc())
            .limit(1)
        )
        run = (await self.session.execute(stmt)).scalar_one_or_none()
        if run is None:
            return None
        failed = await self.session.execute(
            select(HealthCheckRun)
            .where(HealthCheckRun.passed.is_(False))
            .order_by(HealthCheckRun.run_at.desc())
            .limit(5)
        )
        failed_runs = list(failed.scalars().all())
        return {
            "run_id": str(run.id),
            "passed": run.passed,
            "run_at": run.run_at.isoformat(),
            "failed_scenarios": [
                {"run_id": str(r.id), "scenario_id": str(r.scenario_id)}
                for r in failed_runs
                if not r.passed
            ],
        }
