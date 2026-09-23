"""Mock LLM driven by regression fixture files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

from app.db.enums import InvestigationVerdict
from app.llm.schemas import ChatCompletionResult, ToolCallRequest, TokenUsage
from app.skills.submit_conclusion import SUBMIT_CONCLUSION_NAME

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class MockRegressionLLM:
    """Replay fixture steps as tool calls; tracks skills invoked."""

    def __init__(self, case_name: str, *, fallback_verdict: InvestigationVerdict | None = None) -> None:
        self.case_name = case_name
        self.fallback_verdict = fallback_verdict or InvestigationVerdict.LIKELY_FALSE_POSITIVE
        self.skills_called: list[str] = []
        self._steps = self._load_steps()
        self._index = 0
        self.chat = AsyncMock(side_effect=self._next_response)

    def _load_steps(self) -> list[dict[str, Any]]:
        path = FIXTURES_DIR / f"{self.case_name}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return list(data.get("steps", []))
        return [
            {
                "skill": SUBMIT_CONCLUSION_NAME,
                "verdict": self.fallback_verdict.value,
                "reasoning": f"Default mock conclusion for {self.case_name}",
            }
        ]

    async def _next_response(self, **_kwargs: Any) -> ChatCompletionResult:
        if self._index >= len(self._steps):
            step = {
                "skill": SUBMIT_CONCLUSION_NAME,
                "verdict": self.fallback_verdict.value,
                "reasoning": "Fallback submit",
            }
        else:
            step = self._steps[self._index]
            self._index += 1

        skill = step.get("skill", SUBMIT_CONCLUSION_NAME)
        if skill != SUBMIT_CONCLUSION_NAME:
            self.skills_called.append(skill)
            return ChatCompletionResult(
                content=None,
                tool_calls=[
                    ToolCallRequest(
                        id=f"call_{self._index}",
                        name=skill,
                        arguments=step.get("input", {}),
                    )
                ],
                usage=TokenUsage(10, 5),
            )

        arguments = {
            "verdict": step.get("verdict", self.fallback_verdict.value),
            "confidence": step.get("confidence", 0.85),
            "risk_level": step.get("risk_level", "medium"),
            "reasoning": step.get("reasoning", "Mock regression conclusion"),
            "evidence_refs": step.get("evidence_refs", []),
        }
        if step.get("human_query"):
            arguments["human_query"] = step["human_query"]
        return ChatCompletionResult(
            content=None,
            tool_calls=[
                ToolCallRequest(
                    id=f"call_submit_{self._index}",
                    name=SUBMIT_CONCLUSION_NAME,
                    arguments=arguments,
                )
            ],
            usage=TokenUsage(10, 5),
        )


class HealthCheckMockLLM:
    """Immediately submit a fixed verdict for pipeline probes."""

    def __init__(self, verdict: InvestigationVerdict) -> None:
        self.verdict = verdict
        self.skills_called: list[str] = []
        self.chat = AsyncMock(side_effect=self._respond)

    async def _respond(self, **_kwargs: Any) -> ChatCompletionResult:
        return ChatCompletionResult(
            content=None,
            tool_calls=[
                ToolCallRequest(
                    id="hc_submit",
                    name=SUBMIT_CONCLUSION_NAME,
                    arguments={
                        "verdict": self.verdict.value,
                        "confidence": 0.9,
                        "risk_level": "medium",
                        "reasoning": "Health-check mock agent conclusion",
                        "evidence_refs": ["health_check:mock"],
                    },
                )
            ],
            usage=TokenUsage(5, 5),
        )
