"""ReAct Agent loop with native function calling."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from app.core.datetime_utils import utc_now

from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

import app.skills.bootstrap  # noqa: F401 — register skills
from app.agent.closure_evaluator import ClosureConfig, ClosureEvaluator
from app.agent.conclusion import ConclusionPayload, degraded_conclusion, parse_conclusion
from app.agent.config import InvestigationConfig
from app.agent.context import InvestigationContext
from app.agent.prompts import build_initial_messages
from app.defense_assets.disposition.config import load_disposition_config
from app.db.enums import InvestigationStatus, MessageRole
from app.llm.client import LLMClient
from app.models.investigation import Investigation, InvestigationMessage, InvestigationToolCall
from app.skills.registry import SkillRegistry
from app.skills.submit_conclusion import SUBMIT_CONCLUSION_NAME

logger = logging.getLogger(__name__)


@dataclass
class AgentLoopResult:
    conclusion: ConclusionPayload
    investigation_status: InvestigationStatus
    closure_result: Any | None = None
    skills_called: set[str] | None = None


class AgentLoop:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    async def run(
        self,
        session: AsyncSession,
        investigation: Investigation,
        ctx: InvestigationContext,
        config: InvestigationConfig,
    ) -> AgentLoopResult:
        messages = build_initial_messages(ctx)
        tools = SkillRegistry.tool_definitions(include_submit=True)
        disp_config = await load_disposition_config(session)
        if not disp_config.simulation_enabled:
            tools = [t for t in tools if t["function"]["name"] != "simulate_disposition"]
        sequence = 0
        skill_calls = 0
        skills_called: set[str] = set()

        await self._save_message(session, investigation.id, sequence, MessageRole.SYSTEM, messages[0]["content"])
        sequence += 1
        await self._save_message(session, investigation.id, sequence, MessageRole.USER, messages[1]["content"])
        sequence += 1

        for step in range(1, config.max_steps + 1):
            investigation.current_step = step
            try:
                response = await self.llm.chat(
                    messages=messages,
                    tools=tools,
                    model=ctx.model_name,
                )
            except Exception as exc:
                logger.exception("LLM call failed at step %s", step)
                conclusion = degraded_conclusion(f"LLM error: {exc}")
                return AgentLoopResult(conclusion=conclusion, investigation_status=InvestigationStatus.DEGRADED)

            investigation.token_input = (investigation.token_input or 0) + response.usage.prompt_tokens
            investigation.token_output = (investigation.token_output or 0) + response.usage.completion_tokens

            assistant_content = response.content or ""
            if response.tool_calls:
                assistant_msg = {
                    "role": "assistant",
                    "content": assistant_content or None,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments, ensure_ascii=False),
                            },
                        }
                        for call in response.tool_calls
                    ],
                }
                messages.append(assistant_msg)
                await self._save_message(
                    session,
                    investigation.id,
                    sequence,
                    MessageRole.ASSISTANT,
                    json.dumps(assistant_msg, ensure_ascii=False),
                )
                sequence += 1

                for call in response.tool_calls:
                    if call.name == SUBMIT_CONCLUSION_NAME:
                        try:
                            conclusion = parse_conclusion(call.arguments)
                            closure_cfg = ClosureConfig(
                                enabled=config.closure_enabled,
                                min_evidence_closure_score=config.min_evidence_closure_score,
                                min_refutation_coverage_for_attack=config.min_refutation_coverage_for_attack,
                                max_closure_retries=config.max_closure_retries,
                                require_refutation_attempt=config.require_refutation_attempt,
                                min_refuting_hints_checked=config.min_refuting_hints_checked,
                            )
                            hypothesis_template = (
                                ctx.sop.hypothesis_template if ctx.sop else None
                            )
                            closure_result = ClosureEvaluator.evaluate(
                                conclusion,
                                skills_called=skills_called,
                                hypothesis_template=hypothesis_template,
                                config=closure_cfg,
                            )
                            if not closure_result.passed:
                                investigation.closure_retry_count = (
                                    (investigation.closure_retry_count or 0) + 1
                                )
                                if investigation.closure_requested_at is None:
                                    investigation.closure_requested_at = utc_now()
                                if (
                                    investigation.closure_retry_count
                                    > config.max_closure_retries
                                ):
                                    conclusion = degraded_conclusion(
                                        "证据闭合度不足且已达最大补查次数，转人工复核。"
                                    )
                                    investigation.skill_call_count = skill_calls
                                    return AgentLoopResult(
                                        conclusion=conclusion,
                                        investigation_status=InvestigationStatus.NEEDS_HUMAN,
                                        closure_result=closure_result,
                                        skills_called=skills_called,
                                    )
                                err = closure_result.rejection_message()
                                messages.append(
                                    {"role": "tool", "tool_call_id": call.id, "content": err},
                                )
                                await self._save_message(
                                    session,
                                    investigation.id,
                                    sequence,
                                    MessageRole.TOOL,
                                    err,
                                    tool_call_id=call.id,
                                )
                                sequence += 1
                                continue
                            investigation.skill_call_count = skill_calls
                            return AgentLoopResult(
                                conclusion=conclusion,
                                investigation_status=InvestigationStatus.COMPLETED,
                                closure_result=closure_result,
                                skills_called=skills_called,
                            )
                        except ValidationError as exc:
                            err = f"submit_conclusion validation failed: {exc}"
                            messages.append(
                                {"role": "tool", "tool_call_id": call.id, "content": err},
                            )
                            await self._save_message(
                                session,
                                investigation.id,
                                sequence,
                                MessageRole.TOOL,
                                err,
                                tool_call_id=call.id,
                            )
                            sequence += 1
                            continue

                    skill_calls += 1
                    skills_called.add(call.name)
                    if skill_calls > config.max_skill_calls:
                        conclusion = degraded_conclusion("max_skill_calls exceeded")
                        return AgentLoopResult(
                            conclusion=conclusion,
                            investigation_status=InvestigationStatus.NEEDS_HUMAN,
                        )

                    result = await self._execute_skill_with_retry(
                        session,
                        investigation,
                        step,
                        call.name,
                        call.arguments,
                        ctx,
                        config.skill_max_retries,
                    )
                    tool_content = result.summary if result.success else f"Skill error: {result.error or result.summary}"
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": tool_content})
                    await self._save_message(
                        session,
                        investigation.id,
                        sequence,
                        MessageRole.TOOL,
                        tool_content,
                        tool_call_id=call.id,
                    )
                    sequence += 1
                continue

            if assistant_content:
                messages.append({"role": "assistant", "content": assistant_content})
                await self._save_message(
                    session,
                    investigation.id,
                    sequence,
                    MessageRole.ASSISTANT,
                    assistant_content,
                )
                sequence += 1
                messages.append(
                    {
                        "role": "user",
                        "content": "请调用 Skill 收集证据，完成后必须调用 submit_conclusion 提交结论。",
                    }
                )
                await self._save_message(
                    session,
                    investigation.id,
                    sequence,
                    MessageRole.USER,
                    "Reminder: call submit_conclusion when ready.",
                )
                sequence += 1

        investigation.skill_call_count = skill_calls
        conclusion = degraded_conclusion("max_steps exceeded without submit_conclusion")
        return AgentLoopResult(conclusion=conclusion, investigation_status=InvestigationStatus.NEEDS_HUMAN)

    async def _execute_skill_with_retry(
        self,
        session: AsyncSession,
        investigation: Investigation,
        step: int,
        name: str,
        params: dict,
        ctx: InvestigationContext,
        max_retries: int,
    ):
        from app.skills.base import SkillResult

        last: SkillResult | None = None
        for attempt in range(max_retries + 1):
            start = time.perf_counter()
            try:
                last = await SkillRegistry.execute(name, params, ctx, session)
            except Exception as exc:
                last = SkillResult(success=False, summary=str(exc), error="exception")
            latency_ms = int((time.perf_counter() - start) * 1000)
            session.add(
                InvestigationToolCall(
                    investigation_id=investigation.id,
                    step_number=step,
                    skill_name=name,
                    skill_input=params,
                    skill_output=last.data if last else {},
                    output_summary=last.summary if last else None,
                    success=last.success if last else False,
                    retry_count=attempt,
                    latency_ms=latency_ms,
                    called_at=utc_now(),
                )
            )
            if last and last.success:
                return last
        assert last is not None
        return last

    @staticmethod
    async def _save_message(
        session: AsyncSession,
        investigation_id,
        sequence: int,
        role: MessageRole,
        content: str,
        tool_call_id: str | None = None,
    ) -> None:
        session.add(
            InvestigationMessage(
                investigation_id=investigation_id,
                role=role,
                content=content,
                tool_call_id=tool_call_id,
                sequence=sequence,
            )
        )
