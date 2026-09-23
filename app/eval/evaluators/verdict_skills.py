"""Verdict and skill compliance evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from app.db.enums import InvestigationVerdict


@dataclass
class CaseEvalResult:
    case_id: str
    case_name: str
    passed: bool
    expected_verdict: str
    actual_verdict: str | None
    expected_skills: list[str]
    actual_skills: list[str]
    forbidden_skills: list[str]
    verdict_match: bool
    skills_ok: bool
    forbidden_ok: bool
    closure_ok: bool = True
    error: str | None = None


def evaluate_case(
    *,
    case_id: str,
    case_name: str,
    expected_verdict: InvestigationVerdict,
    expected_skills: list,
    forbidden_skills: list | None,
    actual_verdict: InvestigationVerdict | None,
    actual_skills: list[str],
    error: str | None = None,
    require_skills: bool = True,
    require_closure_pass: bool = False,
    closure_passed: bool | None = None,
) -> CaseEvalResult:
    expected_skill_names = [str(s) for s in (expected_skills or [])]
    forbidden = [str(s) for s in (forbidden_skills or [])]
    actual = list(actual_skills)

    verdict_match = actual_verdict == expected_verdict if actual_verdict else False
    skills_ok = all(skill in actual for skill in expected_skill_names)
    forbidden_ok = not any(skill in actual for skill in forbidden)
    if not require_skills:
        skills_ok = True
        forbidden_ok = True
    closure_ok = closure_passed is not False if require_closure_pass else True
    passed = verdict_match and skills_ok and forbidden_ok and closure_ok and error is None

    return CaseEvalResult(
        case_id=case_id,
        case_name=case_name,
        passed=passed,
        expected_verdict=expected_verdict.value,
        actual_verdict=actual_verdict.value if actual_verdict else None,
        expected_skills=expected_skill_names,
        actual_skills=actual,
        forbidden_skills=forbidden,
        verdict_match=verdict_match,
        skills_ok=skills_ok,
        forbidden_ok=forbidden_ok,
        closure_ok=closure_ok,
        error=error,
    )
