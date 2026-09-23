"""Rule-based investigation supervisor (post-submit audit)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.agent.conclusion import ConclusionPayload
from app.models.investigation import InvestigationToolCall


@dataclass
class SupervisorConfig:
    enabled: bool = True
    mode: str = "rules"
    block_on_fail: bool = False
    max_off_sop_skill_calls: int = 3


@dataclass
class SupervisorResult:
    passed: bool
    findings: dict[str, Any] = field(default_factory=dict)

    def to_audit_record(self) -> dict[str, Any]:
        return {"passed": self.passed, **self.findings}


class InvestigationSupervisor:
    @staticmethod
    def audit(
        conclusion: ConclusionPayload,
        tool_calls: list[InvestigationToolCall],
        *,
        config: SupervisorConfig,
        recommended_skills: list[str] | None = None,
    ) -> SupervisorResult:
        if not config.enabled:
            return SupervisorResult(passed=True)

        findings: dict[str, Any] = {}
        issues: list[str] = []

        successful_skills = {tc.skill_name for tc in tool_calls if tc.success}
        if not successful_skills:
            issues.append("no_successful_skill_calls")

        if recommended_skills:
            missing = sorted(set(recommended_skills) - successful_skills)
            if missing:
                issues.append(f"missing_recommended_skills:{','.join(missing)}")
                findings["missing_recommended_skills"] = missing

        sop_skills = set(recommended_skills or []) | {"submit_conclusion"}
        off_sop_calls = [
            tc.skill_name for tc in tool_calls if tc.skill_name and tc.skill_name not in sop_skills
        ]
        if len(off_sop_calls) > config.max_off_sop_skill_calls:
            issues.append("path_drift:too_many_off_sop_skills")
            findings["off_sop_skill_calls"] = off_sop_calls[:10]

        evidence_refs = set(conclusion.evidence_refs or [])
        tool_summaries = " ".join(
            (tc.output_summary or "") for tc in tool_calls if tc.output_summary
        )
        for ref in evidence_refs:
            if ref and ref not in tool_summaries and not any(
                ref in (tc.skill_name or "") for tc in tool_calls
            ):
                issues.append(f"ungrounded_evidence_ref:{ref[:40]}")

        reasoning = conclusion.reasoning or ""
        ipv4_in_reasoning = set(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", reasoning))
        ipv4_in_tools = set(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", tool_summaries))
        hallucinated_ips = ipv4_in_reasoning - ipv4_in_tools
        if hallucinated_ips and conclusion.verdict.value == "attack_confirmed":
            issues.append("possible_hallucinated_ip")
            findings["hallucinated_ips"] = sorted(hallucinated_ips)[:5]

        findings["issues"] = issues
        findings["successful_skills"] = sorted(successful_skills)
        passed = len(issues) == 0 or not any(
            i.startswith("ungrounded_")
            or i == "possible_hallucinated_ip"
            or i.startswith("missing_recommended_skills:")
            or i.startswith("path_drift:")
            for i in issues
        )
        return SupervisorResult(passed=passed, findings=findings)
