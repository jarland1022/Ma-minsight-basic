"""Batch regression test execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from app.core.datetime_utils import utc_now
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.skills.bootstrap  # noqa: F401
from app.agent.config import InvestigationConfig
from app.agent.loop import AgentLoop
from app.db.enums import ActorType, InvestigationVerdict
from app.defense_assets.disposition.config import DispositionConfig
from app.eval.config import load_eval_config
from app.services.system_config import get_config_bool
from app.eval.evaluators.metrics import compute_regression_metrics
from app.eval.evaluators.verdict_skills import CaseEvalResult, evaluate_case
from app.eval.lock import regression_lock
from app.eval.notifications import notify_eval_failure
from app.eval.regression.alert_builder import build_regression_context
from app.eval.regression.mock_llm import MockRegressionLLM
from app.llm.client import LLMClient
from app.models.cache_eval import RegressionTestCase, RegressionTestRun
from app.models.system import AuditLog

logger = logging.getLogger(__name__)


@dataclass
class RegressionRunResult:
    run_id: UUID | None = None
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped_lock: bool = False
    errors: list[str] = field(default_factory=list)


class RegressionRunner:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(
        self,
        *,
        trigger: str = "manual",
        tag: str | None = None,
        use_real_llm: bool | None = None,
        use_lock: bool = True,
    ) -> RegressionRunResult:
        result = RegressionRunResult()

        async def _execute() -> RegressionRunResult:
            config = await load_eval_config(self.session)
            require_closure = await get_config_bool(
                self.session, "eval.require_closure_pass_for_regression", True
            )
            if not config.regression_enabled:
                result.errors.append("regression disabled")
                return result

            real_llm = (
                use_real_llm
                if use_real_llm is not None
                else config.regression_use_real_llm_default
            )
            cases = await self._load_cases(tag)
            if not cases:
                result.errors.append("no active regression cases")
                return result

            case_results: list[CaseEvalResult] = []
            for case in cases:
                case_results.append(
                    await self._run_case(case, use_real_llm=real_llm, require_closure=require_closure)
                )

            metrics = compute_regression_metrics(case_results)
            run = RegressionTestRun(
                trigger=trigger,
                model_name="deepseek-chat" if real_llm else "mock-regression",
                sop_version=None,
                total=metrics["total"],
                passed=metrics["passed"],
                failed=metrics["failed"],
                metrics=metrics,
                details={
                    "cases": [
                        {
                            "case_id": r.case_id,
                            "case_name": r.case_name,
                            "passed": r.passed,
                            "expected_verdict": r.expected_verdict,
                            "actual_verdict": r.actual_verdict,
                            "expected_skills": r.expected_skills,
                            "actual_skills": r.actual_skills,
                            "forbidden_skills": r.forbidden_skills,
                            "verdict_match": r.verdict_match,
                            "skills_ok": r.skills_ok,
                            "forbidden_ok": r.forbidden_ok,
                            "closure_ok": r.closure_ok,
                            "error": r.error,
                        }
                        for r in case_results
                    ]
                },
                run_at=utc_now(),
            )
            self.session.add(run)
            self.session.add(
                AuditLog(
                    actor_type=ActorType.SYSTEM,
                    action="regression.completed" if metrics["failed"] == 0 else "regression.failed",
                    resource_type="regression",
                    resource_id="global",
                    detail={"passed": metrics["passed"], "failed": metrics["failed"]},
                )
            )
            await self.session.commit()
            await self.session.refresh(run)

            result.run_id = run.id
            result.total = metrics["total"]
            result.passed = metrics["passed"]
            result.failed = metrics["failed"]

            if metrics["failed"] > 0:
                await notify_eval_failure(
                    self.session,
                    title="Regression test failed",
                    detail=f"{metrics['failed']}/{metrics['total']} cases failed",
                )
            return result

        if use_lock:
            async with regression_lock() as acquired:
                if not acquired:
                    result.skipped_lock = True
                    return result
                return await _execute()
        return await _execute()

    async def _load_cases(self, tag: str | None) -> list[RegressionTestCase]:
        stmt = select(RegressionTestCase).where(RegressionTestCase.is_active.is_(True))
        if tag:
            stmt = stmt.where(RegressionTestCase.tags.contains([tag]))
        stmt = stmt.order_by(RegressionTestCase.name)
        return list((await self.session.execute(stmt)).scalars().all())

    async def _run_case(
        self,
        case: RegressionTestCase,
        *,
        use_real_llm: bool,
        require_closure: bool = False,
    ) -> CaseEvalResult:
        investigation, ctx = build_regression_context(case.name, case.alert_payload)
        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        if use_real_llm:
            llm: Any = LLMClient()
            skills_called: list[str] = []
        else:
            mock_llm = MockRegressionLLM(case.name, fallback_verdict=case.expected_verdict)
            llm = mock_llm
            skills_called = mock_llm.skills_called

        loop = AgentLoop(llm=llm)
        inv_config = InvestigationConfig(
            max_steps=20,
            max_skill_calls=40,
            model_name=ctx.model_name,
        )

        try:
            import app.agent.loop as loop_module

            disp_mock = AsyncMock(return_value=DispositionConfig())
            with patch("app.agent.loop.load_disposition_config", disp_mock):
                if not use_real_llm:

                    async def mock_execute(name, params, ctx, session):
                        from app.skills.base import SkillResult

                        skills_called.append(name)
                        return SkillResult(
                            success=True,
                            summary=f"mock {name}",
                            evidence_ref=f"mock:{name}",
                        )

                    original = loop_module.SkillRegistry.execute
                    loop_module.SkillRegistry.execute = mock_execute
                    try:
                        loop_result = await loop.run(
                            mock_session, investigation, ctx, inv_config
                        )
                    finally:
                        loop_module.SkillRegistry.execute = original
                else:
                    loop_result = await loop.run(self.session, investigation, ctx, inv_config)

            actual_skills = list(loop_result.skills_called or skills_called)
            closure_passed = (
                loop_result.closure_result.passed
                if loop_result.closure_result is not None
                else None
            )
            return evaluate_case(
                case_id=str(case.id),
                case_name=case.name,
                expected_verdict=case.expected_verdict,
                expected_skills=list(case.expected_skills or []),
                forbidden_skills=list(case.forbidden_skills or []) if case.forbidden_skills else [],
                actual_verdict=loop_result.conclusion.verdict,
                actual_skills=actual_skills,
                require_skills=not use_real_llm,
                require_closure_pass=require_closure,
                closure_passed=closure_passed,
            )
        except Exception as exc:
            logger.exception("Regression case failed: %s", case.name)
            return evaluate_case(
                case_id=str(case.id),
                case_name=case.name,
                expected_verdict=case.expected_verdict,
                expected_skills=list(case.expected_skills or []),
                forbidden_skills=list(case.forbidden_skills or []) if case.forbidden_skills else [],
                actual_verdict=None,
                actual_skills=[],
                error=str(exc),
            )
