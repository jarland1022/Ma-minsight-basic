"""Evidence closure evaluation before accepting submit_conclusion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agent.conclusion import ConclusionPayload
from app.db.enums import InvestigationVerdict


@dataclass
class ClosureConfig:
    enabled: bool = True
    min_evidence_closure_score: float = 0.6
    min_refutation_coverage_for_attack: float = 0.5
    max_closure_retries: int = 2
    require_refutation_attempt: bool = True
    min_refuting_hints_checked: int = 1


@dataclass
class ClosureResult:
    passed: bool
    evidence_closure_score: float
    refutation_coverage: float
    checks: dict[str, Any] = field(default_factory=dict)
    rejection_reasons: list[str] = field(default_factory=list)

    def rejection_message(self) -> str:
        if self.passed:
            return ""
        lines = ["submit_conclusion 被拒绝：证据闭合度不足，请补充调查后再提交。"]
        lines.extend(f"- {reason}" for reason in self.rejection_reasons)
        if self.checks.get("missing_skills"):
            lines.append(f"缺少 Skill 调用: {', '.join(self.checks['missing_skills'])}")
        return "\n".join(lines)


class ClosureEvaluator:
    @staticmethod
    def evaluate(
        conclusion: ConclusionPayload,
        *,
        skills_called: set[str],
        hypothesis_template: dict[str, Any] | None,
        config: ClosureConfig,
    ) -> ClosureResult:
        if not config.enabled:
            return ClosureResult(passed=True, evidence_closure_score=1.0, refutation_coverage=1.0)

        if conclusion.verdict in {
            InvestigationVerdict.INSUFFICIENT_INFORMATION,
            InvestigationVerdict.NEEDS_HUMAN_REVIEW,
        }:
            return ClosureResult(
                passed=True,
                evidence_closure_score=1.0,
                refutation_coverage=1.0,
                checks={"exempt_verdict": conclusion.verdict.value},
            )

        template = hypothesis_template or {}
        required_skills = list(template.get("required_skills_before_conclude") or [])
        supporting = list(template.get("supporting_hints") or [])
        refuting = list(template.get("refuting_hints") or [])

        missing_skills = [s for s in required_skills if s not in skills_called]
        required_coverage = (
            1.0 - (len(missing_skills) / len(required_skills)) if required_skills else 1.0
        )

        supporting_matched = sum(
            1 for hint in supporting if hint.get("skill") in skills_called
        )
        supporting_score = supporting_matched / len(supporting) if supporting else 1.0

        refuting_attempted = sum(
            1 for hint in refuting if hint.get("skill") in skills_called
        )
        refutation_coverage = refuting_attempted / len(refuting) if refuting else 1.0

        evidence_closure_score = (
            0.4 * required_coverage + 0.3 * supporting_score + 0.3 * refutation_coverage
        )

        checks: dict[str, Any] = {
            "required_skills_coverage": required_coverage,
            "supporting_hints_matched": supporting_matched,
            "refuting_hints_attempted": refuting_attempted,
            "missing_skills": missing_skills,
        }

        rejection_reasons: list[str] = []
        passed = True

        if evidence_closure_score < config.min_evidence_closure_score:
            passed = False
            rejection_reasons.append(
                f"证据闭合度 {evidence_closure_score:.2f} 低于门槛 "
                f"{config.min_evidence_closure_score:.2f}"
            )

        if missing_skills:
            passed = False
            rejection_reasons.append(f"未调用必填 Skill: {', '.join(missing_skills)}")

        if (
            conclusion.verdict == InvestigationVerdict.ATTACK_CONFIRMED
            and config.require_refutation_attempt
            and refuting
            and refuting_attempted < config.min_refuting_hints_checked
        ):
            passed = False
            rejection_reasons.append(
                "确认攻击前需至少尝试一条反证调查（如 query_asset / query_entity_graph）"
            )

        if (
            conclusion.verdict == InvestigationVerdict.ATTACK_CONFIRMED
            and refutation_coverage < config.min_refutation_coverage_for_attack
            and refuting
        ):
            passed = False
            rejection_reasons.append(
                f"反证覆盖率 {refutation_coverage:.2f} 低于攻击确认门槛 "
                f"{config.min_refutation_coverage_for_attack:.2f}"
            )

        return ClosureResult(
            passed=passed,
            evidence_closure_score=evidence_closure_score,
            refutation_coverage=refutation_coverage,
            checks=checks,
            rejection_reasons=rejection_reasons,
        )
