"""Investigation failure classification helpers (P0-03 / P0-05)."""

from __future__ import annotations

from app.db.enums import InvestigationFailureClass, InvestigationStatus, InvestigationVerdict

OPS_FAILURE_CLASSES = frozenset(
    {
        InvestigationFailureClass.LLM_SERVICE.value,
        InvestigationFailureClass.REQUIRED_SKILL.value,
        InvestigationFailureClass.DATASOURCE.value,
    }
)

DETERMINISTIC_VERDICTS = frozenset(
    {
        InvestigationVerdict.ATTACK_CONFIRMED,
        InvestigationVerdict.LIKELY_FALSE_POSITIVE,
    }
)

DATASOURCE_ERROR_MARKERS = (
    "timeout",
    "timed out",
    "connection",
    "connect",
    "unreachable",
    "503",
    "502",
    "504",
    "econnrefused",
    "name or service not known",
    "temporary failure",
)


def is_ops_failure_class(failure_class: str | None) -> bool:
    if not failure_class:
        return False
    return failure_class in OPS_FAILURE_CLASSES


def classify_llm_error(exc: BaseException) -> tuple[str, str]:
    """Return (failure_class, error_code) for an LLM client exception."""
    msg = str(exc).lower()
    if "egress" in msg or "channel_disabled" in msg or "pseudonym_secret_missing" in msg:
        return InvestigationFailureClass.LLM_SERVICE.value, "llm_egress_denied"
    if "deepseek_api_key is not configured" in msg or "api key" in msg and "not configured" in msg:
        return InvestigationFailureClass.LLM_SERVICE.value, "llm_not_configured"
    if "404" in msg:
        return InvestigationFailureClass.LLM_SERVICE.value, "llm_http_404"
    if "401" in msg or "403" in msg:
        return InvestigationFailureClass.LLM_SERVICE.value, "llm_http_auth"
    if "500" in msg or "502" in msg or "503" in msg or "504" in msg:
        return InvestigationFailureClass.LLM_SERVICE.value, "llm_http_5xx"
    if "timeout" in msg or "timed out" in msg:
        return InvestigationFailureClass.LLM_SERVICE.value, "llm_timeout"
    return InvestigationFailureClass.LLM_SERVICE.value, "llm_error"


def classify_skill_error(error: str | None, *, required: bool) -> str:
    text = (error or "").lower()
    if any(m in text for m in DATASOURCE_ERROR_MARKERS):
        return InvestigationFailureClass.DATASOURCE.value
    if required:
        return InvestigationFailureClass.REQUIRED_SKILL.value
    return InvestigationFailureClass.OPTIONAL_SKILL.value


def blocks_auto_pick(*, status: InvestigationStatus | str, failure_class: str | None) -> bool:
    """Latest investigation should block scheduler auto re-pick."""
    status_val = status.value if isinstance(status, InvestigationStatus) else str(status)
    if status_val == InvestigationStatus.FAILED.value:
        return True
    if status_val == InvestigationStatus.DEGRADED.value and is_ops_failure_class(failure_class):
        return True
    return False


def rejects_deterministic_verdict(
    verdict: InvestigationVerdict,
    *,
    failed_required_skills: set[str] | list[str],
) -> bool:
    if verdict not in DETERMINISTIC_VERDICTS:
        return False
    return bool(failed_required_skills)
