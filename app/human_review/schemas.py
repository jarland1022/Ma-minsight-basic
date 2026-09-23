"""Human review DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass
class ReviewMessagePayload:
    request_id: UUID
    event_id: UUID
    short_code: str
    markdown: str
    to_user: str


@dataclass
class SendResult:
    success: bool
    external_msg_id: str | None = None
    error: str | None = None
    used_fallback: bool = False


@dataclass
class InboundReply:
    raw_content: str
    external_msg_id: str | None = None
    responder: str | None = None
