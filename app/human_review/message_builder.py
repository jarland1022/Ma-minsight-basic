"""Build outbound IM messages for human review."""

from __future__ import annotations

from uuid import UUID

from app.db.enums import InvestigationVerdict
from app.human_review.schemas import ReviewMessagePayload
from app.models.investigation import Event, InvestigationConclusion


def event_short_code(event_id: UUID) -> str:
    return str(event_id).replace("-", "")[:8].lower()


def request_short_code(request_id: UUID) -> str:
    return str(request_id).replace("-", "")[:8].lower()


def build_review_message(
    *,
    request_id: UUID,
    event: Event,
    conclusion: InvestigationConclusion,
    to_user: str,
    max_chars: int = 1800,
) -> ReviewMessagePayload:
    short = request_short_code(request_id)
    missing = conclusion.missing_info or []
    missing_lines = "\n".join(f"- {item}" for item in missing[:5]) or "- （无）"

    verdict_label = {
        InvestigationVerdict.INSUFFICIENT_INFORMATION: "信息不足",
        InvestigationVerdict.NEEDS_HUMAN_REVIEW: "需人工复核",
    }.get(conclusion.verdict, conclusion.verdict.value)

    body = f"""## 安全告警协查请求

**事件** {event.title or event.primary_category} | 风险 {event.risk_score:.0f} | {event.primary_category or "-"}
**主机** {event.aggregate_host_name or "-"} | **用户** {event.aggregate_user_name or "-"}
**Agent 结论** {verdict_label}（置信度 {conclusion.confidence:.2f}）

**已知推理**
{(conclusion.reasoning or "")[:500]}

**缺失信息**
{missing_lines}

**请协助确认**
{conclusion.human_query or "请补充现场情况。"}

---
请回复并保留标签：`#EVT-{short}`
协查单号：{short}
"""
    if len(body) > max_chars:
        body = body[: max_chars - 20] + "\n...(已截断)"

    return ReviewMessagePayload(
        request_id=request_id,
        event_id=event.id,
        short_code=short,
        markdown=body,
        to_user=to_user,
    )
