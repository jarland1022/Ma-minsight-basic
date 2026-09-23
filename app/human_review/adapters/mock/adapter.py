"""Mock IM adapter for tests and dev without WeCom."""

from __future__ import annotations

import uuid

from app.db.enums import ImChannel
from app.human_review.adapters.base import ImChannelAdapter
from app.human_review.schemas import InboundReply, ReviewMessagePayload, SendResult

_sent_messages: list[ReviewMessagePayload] = []


class MockImAdapter(ImChannelAdapter):
    channel = ImChannel.WECOM

    async def send_review_request(self, payload: ReviewMessagePayload) -> SendResult:
        _sent_messages.append(payload)
        return SendResult(success=True, external_msg_id=f"mock-{uuid.uuid4().hex[:12]}")

    @staticmethod
    def drain_sent() -> list[ReviewMessagePayload]:
        messages = list(_sent_messages)
        _sent_messages.clear()
        return messages

    @staticmethod
    def clear() -> None:
        _sent_messages.clear()
