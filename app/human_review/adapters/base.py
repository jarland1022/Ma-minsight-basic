"""IM channel adapter base."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.db.enums import ImChannel
from app.human_review.schemas import InboundReply, ReviewMessagePayload, SendResult


class ImChannelAdapter(ABC):
    channel: ImChannel

    @abstractmethod
    async def send_review_request(self, payload: ReviewMessagePayload) -> SendResult:
        raise NotImplementedError

    def verify_callback(self, *, msg_signature: str, timestamp: str, nonce: str, echo_str: str) -> bool:
        return False

    async def parse_callback_body(self, body: dict | str) -> InboundReply | None:
        return None
