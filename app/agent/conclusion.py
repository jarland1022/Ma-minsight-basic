"""Conclusion payload validation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.db.enums import InvestigationVerdict, RiskLevel

EvidenceStrength = Literal["none", "single_path", "multi_path"]
DispositionGrade = Literal[
    "confirmed_compromise",
    "suspicious",
    "false_positive",
    "needs_more_evidence",
]


class SuggestedAssets(BaseModel):
    judgment_case: dict[str, Any] | None = None
    whitelist_candidate: dict[str, Any] | None = None
    profile_update: dict[str, Any] | None = None


class ConclusionPayload(BaseModel):
    verdict: InvestigationVerdict
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    reasoning: str
    recommended_action: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    evidence_strength: EvidenceStrength | None = None
    disposition_grade: DispositionGrade | None = None
    human_query: str | None = None
    missing_info: list[str] = Field(default_factory=list)
    suggested_assets: SuggestedAssets = Field(default_factory=SuggestedAssets)
    hypotheses_evaluated: list[dict[str, Any]] = Field(default_factory=list)
    refutation_summary: str | None = None

    @model_validator(mode="after")
    def require_human_query_for_insufficient(self) -> ConclusionPayload:
        if (
            self.verdict == InvestigationVerdict.INSUFFICIENT_INFORMATION
            and not self.human_query
        ):
            raise ValueError("human_query is required when verdict is insufficient_information")
        return self

    @model_validator(mode="after")
    def enforce_multi_path_for_attack(self) -> ConclusionPayload:
        if self.verdict == InvestigationVerdict.ATTACK_CONFIRMED:
            strength = self.evidence_strength or "single_path"
            self.evidence_strength = strength  # type: ignore[assignment]
            if strength != "multi_path":
                raise ValueError(
                    "attack_confirmed requires evidence_strength=multi_path "
                    "(至少两路独立证据交叉验证)"
                )
            if self.disposition_grade is None:
                self.disposition_grade = "confirmed_compromise"
        elif self.disposition_grade is None:
            mapping: dict[InvestigationVerdict, DispositionGrade] = {
                InvestigationVerdict.LIKELY_FALSE_POSITIVE: "false_positive",
                InvestigationVerdict.INSUFFICIENT_INFORMATION: "needs_more_evidence",
                InvestigationVerdict.NEEDS_HUMAN_REVIEW: "suspicious",
            }
            mapped = mapping.get(self.verdict)
            if mapped:
                self.disposition_grade = mapped
        if (
            self.evidence_strength == "single_path"
            and self.verdict == InvestigationVerdict.ATTACK_CONFIRMED
        ):
            raise ValueError("single_path evidence cannot support attack_confirmed")
        return self


def parse_conclusion(params: dict[str, Any]) -> ConclusionPayload:
    suggested = params.get("suggested_assets") or {}
    if not isinstance(suggested, dict):
        suggested = {}
    payload = {
        **params,
        "suggested_assets": SuggestedAssets(
            judgment_case=suggested.get("judgment_case"),
            whitelist_candidate=suggested.get("whitelist_candidate"),
            profile_update=suggested.get("profile_update"),
        ),
    }
    return ConclusionPayload.model_validate(payload)


def degraded_conclusion(reason: str) -> ConclusionPayload:
    return ConclusionPayload(
        verdict=InvestigationVerdict.NEEDS_HUMAN_REVIEW,
        confidence=0.0,
        risk_level=RiskLevel.MEDIUM,
        reasoning=reason,
        recommended_action="建议人工复核该事件",
        missing_info=[reason],
        human_query=f"自动调查未完成：{reason}，请协助确认。",
        evidence_strength="none",
        disposition_grade="needs_more_evidence",
    )
