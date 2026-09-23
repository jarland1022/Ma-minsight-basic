"""Human review orchestration: dispatch, expire, handle replies."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from app.core.config import settings
from app.core.datetime_utils import hours_ago, utc_now
from uuid import UUID, uuid4

from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import app.human_review.adapters.bootstrap  # noqa: F401
from app.db.enums import (
    ActorType,
    EventStatus,
    HumanReviewStatus,
    ImChannel,
    InvestigationStatus,
    InvestigationVerdict,
)
from app.human_review.adapters.registry import ImAdapterRegistry
from app.human_review.config import HumanReviewConfig, load_human_review_config
from app.human_review.lock import human_review_lock
from app.human_review.message_builder import build_review_message
from app.human_review.reinvestigation import mark_reinvestigation
from app.human_review.stale import cancel_all_obsolete_sent_reviews, cancel_obsolete_sent_reviews_for_event
from app.eval.probe.guard import event_is_probe
from app.human_review.reply_parser import parse_reply_content
from app.human_review.schemas import InboundReply
from app.models.human_review import HumanReviewRequest, HumanReviewResponse
from app.models.investigation import Event, Investigation, InvestigationConclusion
from app.models.system import AuditLog

logger = logging.getLogger(__name__)

HUMAN_VERDICTS = (
    InvestigationVerdict.INSUFFICIENT_INFORMATION,
    InvestigationVerdict.NEEDS_HUMAN_REVIEW,
)


def _im_channel_configured(config: HumanReviewConfig) -> bool:
    if config.channel != "wecom":
        return True
    return bool(settings.wecom_corp_id and settings.wecom_secret) or bool(settings.wecom_webhook_url)


@dataclass
class HumanReviewRunResult:
    dispatched: int = 0
    expired: int = 0
    cancelled_obsolete: int = 0
    skipped_lock: bool = False
    skipped_disabled: bool = False
    skipped_not_configured: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class HandleReplyResult:
    request_id: UUID | None = None
    event_id: UUID | None = None
    reinvestigation_triggered: bool = False
    error: str | None = None


class HumanReviewService:
    def __init__(self, session: AsyncSession, *, channel: str | None = None) -> None:
        self.session = session
        self._channel_override = channel

    async def run(self, *, limit: int | None = None, use_lock: bool = True) -> HumanReviewRunResult:
        result = HumanReviewRunResult()

        async def _execute() -> HumanReviewRunResult:
            config = await load_human_review_config(self.session)
            if not config.enabled:
                result.skipped_disabled = True
                return result

            result.expired = await self._expire_stale_requests(config)
            result.cancelled_obsolete = await cancel_all_obsolete_sent_reviews(self.session)

            web_inbox_only = config.channel == "wecom" and not _im_channel_configured(config)
            if web_inbox_only:
                logger.info(
                    "WeCom not configured; dispatching to Web 协查 inbox only "
                    "(set WECOM_CORP_ID/SECRET or WECOM_WEBHOOK_URL for IM push)"
                )

            batch = limit or config.batch_size
            candidates = await self._pick_dispatch_candidates(batch, config)
            adapter = self._adapter(config, web_inbox_only=web_inbox_only)

            for event, investigation, conclusion in candidates:
                try:
                    await self._dispatch_one(event, investigation, conclusion, config, adapter)
                    result.dispatched += 1
                except Exception as exc:
                    result.errors.append(f"{event.id}: {exc}")
                    logger.exception("Human review dispatch failed for event=%s", event.id)

            if result.dispatched or result.expired or result.cancelled_obsolete:
                self.session.add(
                    AuditLog(
                        actor_type=ActorType.SYSTEM,
                        action="human_review.batch_completed",
                        resource_type="human_review",
                        resource_id="global",
                        detail={
                            "dispatched": result.dispatched,
                            "expired": result.expired,
                            "cancelled_obsolete": result.cancelled_obsolete,
                            "errors": len(result.errors),
                        },
                    )
                )
            await self.session.commit()
            return result

        if use_lock:
            async with human_review_lock() as acquired:
                if not acquired:
                    result.skipped_lock = True
                    return result
                return await _execute()
        return await _execute()

    async def handle_reply(
        self,
        *,
        raw_content: str,
        external_msg_id: str | None = None,
        responder: str | None = None,
        request_id: UUID | None = None,
    ) -> HandleReplyResult:
        config = await load_human_review_config(self.session)
        result = HandleReplyResult()

        if request_id is not None:
            req = await self.session.get(HumanReviewRequest, request_id)
            if req is None or req.status != HumanReviewStatus.SENT:
                result.error = "Request not found or not awaiting reply"
                return result
        else:
            short_code, parsed_body = parse_reply_content(raw_content)
            if short_code is None:
                result.error = "Missing #EVT- tag in reply"
                return result
            req = await self._find_request_by_short_code(short_code)
            if req is None:
                result.error = f"No active request for #EVT-{short_code}"
                return result
            raw_content = parsed_body

        if await self._response_exists(req.id, external_msg_id, raw_content):
            result.request_id = req.id
            result.event_id = req.event_id
            result.error = "Duplicate response ignored"
            return result

        _, cleaned = parse_reply_content(raw_content)
        response = HumanReviewResponse(
            request_id=req.id,
            responder=responder,
            raw_content=raw_content,
            parsed_content=cleaned,
            triggered_reinvestigation=config.reinvestigation_enabled,
        )
        self.session.add(response)

        req.status = HumanReviewStatus.ANSWERED
        req.answered_at = utc_now()

        event = await self.session.get(Event, req.event_id)
        if event and config.reinvestigation_enabled:
            await mark_reinvestigation(event.id)
            event.status = EventStatus.PENDING_REVIEW
            result.reinvestigation_triggered = True

        investigation = await self.session.get(Investigation, req.investigation_id)
        if investigation and investigation.status == InvestigationStatus.NEEDS_HUMAN:
            investigation.status = InvestigationStatus.COMPLETED

        await self.session.commit()
        result.request_id = req.id
        result.event_id = req.event_id
        return result

    async def cancel_request(self, request_id: UUID) -> bool:
        req = await self.session.get(HumanReviewRequest, request_id)
        if req is None or req.status != HumanReviewStatus.SENT:
            return False
        req.status = HumanReviewStatus.CANCELLED
        await self.session.commit()
        return True

    async def get_request_detail(self, request_id: UUID) -> dict | None:
        result = await self.session.execute(
            select(HumanReviewRequest)
            .options(selectinload(HumanReviewRequest.responses))
            .where(HumanReviewRequest.id == request_id)
        )
        req = result.scalar_one_or_none()
        if req is None:
            return None
        return {
            "id": str(req.id),
            "event_id": str(req.event_id),
            "investigation_id": str(req.investigation_id),
            "channel": req.channel.value,
            "status": req.status.value,
            "question": req.question,
            "context_summary": req.context_summary,
            "external_msg_id": req.external_msg_id,
            "sent_at": req.sent_at.isoformat() if req.sent_at else None,
            "answered_at": req.answered_at.isoformat() if req.answered_at else None,
            "responses": [
                {
                    "id": str(r.id),
                    "responder": r.responder,
                    "raw_content": r.raw_content,
                    "parsed_content": r.parsed_content,
                    "triggered_reinvestigation": r.triggered_reinvestigation,
                    "created_at": r.created_at.isoformat(),
                }
                for r in req.responses
            ],
        }

    async def stats(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for status in HumanReviewStatus:
            result = await self.session.execute(
                select(func.count()).select_from(HumanReviewRequest).where(HumanReviewRequest.status == status)
            )
            counts[status.value] = int(result.scalar_one() or 0)
        return counts

    def _adapter(self, config: HumanReviewConfig, *, web_inbox_only: bool = False):
        if web_inbox_only:
            return ImAdapterRegistry.create("mock")
        channel = self._channel_override or config.channel
        return ImAdapterRegistry.create(channel)

    async def _pick_dispatch_candidates(
        self,
        limit: int,
        config: HumanReviewConfig,
    ) -> list[tuple[Event, Investigation, InvestigationConclusion]]:
        sent_exists = (
            select(HumanReviewRequest.id)
            .where(
                HumanReviewRequest.event_id == Event.id,
                HumanReviewRequest.status == HumanReviewStatus.SENT,
            )
            .correlate(Event)
            .exists()
        )
        request_count = (
            select(func.count())
            .select_from(HumanReviewRequest)
            .where(HumanReviewRequest.event_id == Event.id)
            .correlate(Event)
            .scalar_subquery()
        )

        stmt = (
            select(Event)
            .where(
                Event.status == EventStatus.HUMAN_PENDING,
                ~sent_exists,
                request_count <= config.max_resend,
            )
            .order_by(Event.queue_priority.desc(), Event.risk_score.desc(), Event.last_alert_at.asc())
            .limit(limit)
        )
        events_result = await self.session.execute(stmt)
        events = list(events_result.scalars().all())

        candidates: list[tuple[Event, Investigation, InvestigationConclusion]] = []
        for event in events:
            if await event_is_probe(self.session, event.id):
                continue
            inv_conclusion = await self._latest_human_investigation(event.id)
            if inv_conclusion is None:
                continue
            investigation, conclusion = inv_conclusion
            candidates.append((event, investigation, conclusion))
        return candidates

    async def _latest_human_investigation(
        self, event_id: UUID
    ) -> tuple[Investigation, InvestigationConclusion] | None:
        stmt = (
            select(Investigation)
            .options(selectinload(Investigation.conclusion))
            .where(Investigation.event_id == event_id)
            .order_by(Investigation.started_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        investigation = result.scalar_one_or_none()
        if investigation is None or investigation.conclusion is None:
            return None
        if investigation.conclusion.verdict not in HUMAN_VERDICTS:
            return None
        return investigation, investigation.conclusion

    async def _dispatch_one(
        self,
        event: Event,
        investigation: Investigation,
        conclusion: InvestigationConclusion,
        config: HumanReviewConfig,
        adapter,
    ) -> None:
        request_id = uuid4()
        payload = build_review_message(
            request_id=request_id,
            event=event,
            conclusion=conclusion,
            to_user=config.wecom_to_user,
            max_chars=config.message_max_chars,
        )
        send_result = await adapter.send_review_request(payload)
        if not send_result.success:
            raise RuntimeError(send_result.error or "IM send failed")

        try:
            channel = ImChannel(config.channel)
        except ValueError:
            channel = ImChannel.WECOM

        now = utc_now()
        self.session.add(
            HumanReviewRequest(
                id=request_id,
                investigation_id=investigation.id,
                event_id=event.id,
                channel=channel,
                question=conclusion.human_query or "请协助确认该事件。",
                context_summary=payload.markdown,
                status=HumanReviewStatus.SENT,
                external_msg_id=send_result.external_msg_id,
                sent_at=now,
            )
        )
        investigation.status = InvestigationStatus.NEEDS_HUMAN

    async def _expire_stale_requests(self, config: HumanReviewConfig) -> int:
        cutoff = hours_ago(config.timeout_hours)
        result = await self.session.execute(
            select(HumanReviewRequest).where(
                HumanReviewRequest.status == HumanReviewStatus.SENT,
                HumanReviewRequest.sent_at.is_not(None),
                HumanReviewRequest.sent_at < cutoff,
            )
        )
        expired_rows = list(result.scalars().all())
        for req in expired_rows:
            req.status = HumanReviewStatus.EXPIRED
        return len(expired_rows)

    async def _find_request_by_short_code(self, short_code: str) -> HumanReviewRequest | None:
        id_text = func.replace(cast(HumanReviewRequest.id, String), "-", "")
        stmt = (
            select(HumanReviewRequest)
            .where(
                HumanReviewRequest.status == HumanReviewStatus.SENT,
                id_text.like(f"{short_code}%"),
            )
            .order_by(HumanReviewRequest.sent_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _response_exists(
        self,
        request_id: UUID,
        external_msg_id: str | None,
        raw_content: str,
    ) -> bool:
        if external_msg_id:
            existing = await self.session.execute(
                select(HumanReviewResponse).where(
                    HumanReviewResponse.request_id == request_id,
                    HumanReviewResponse.raw_content == raw_content,
                )
            )
            if existing.scalar_one_or_none():
                return True
        return False
