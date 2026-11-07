"""Conclusion payload validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.db.enums import InvestigationVerdict, RiskLevel


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


def security_incomplete_conclusion(reason: str) -> ConclusionPayload:
    """Security / evidence gap → may enter Human Review (not used for ops/LLM failures)."""
    return ConclusionPayload(
        verdict=InvestigationVerdict.NEEDS_HUMAN_REVIEW,
        confidence=0.0,
        risk_level=RiskLevel.MEDIUM,
        reasoning=reason,
        recommended_action="建议人工复核该事件",
        missing_info=[reason],
        human_query=f"调查证据不足：{reason}，请协助确认。",
    )


def degraded_conclusion(reason: str) -> ConclusionPayload:
    """Backward-compatible alias for security-incomplete conclusions.

    Do **not** use for LLM/config/ops failures — those must not create Human Review.
    """
    return security_incomplete_conclusion(reason)
