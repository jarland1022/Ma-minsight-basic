"""WeCom corp app adapter with webhook fallback for outbound."""

from __future__ import annotations

import hashlib
import logging
import time
import uuid

import httpx

from app.core.config import settings
from app.db.enums import ImChannel
from app.human_review.adapters.base import ImChannelAdapter
from app.human_review.schemas import InboundReply, ReviewMessagePayload, SendResult

logger = logging.getLogger(__name__)

_TOKEN_CACHE: dict[str, tuple[str, float]] = {}


class WeComAdapter(ImChannelAdapter):
    channel = ImChannel.WECOM

    async def send_review_request(self, payload: ReviewMessagePayload) -> SendResult:
        if settings.wecom_corp_id and settings.wecom_secret:
            result = await self._send_via_corp_app(payload)
            if result.success:
                return result
            logger.warning("WeCom corp app send failed: %s; trying webhook fallback", result.error)

        if settings.wecom_webhook_url:
            return await self._send_via_webhook(payload)

        return SendResult(
            success=False,
            error="WeCom not configured (set WECOM_CORP_ID/SECRET or WECOM_WEBHOOK_URL)",
        )

    async def _send_via_corp_app(self, payload: ReviewMessagePayload) -> SendResult:
        token = await self._get_access_token()
        if token is None:
            return SendResult(success=False, error="Failed to obtain WeCom access token")

        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
        body = {
            "touser": payload.to_user,
            "msgtype": "markdown",
            "agentid": int(settings.wecom_agent_id),
            "markdown": {"content": payload.markdown},
            "safe": 0,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=body)
            data = response.json()

        if data.get("errcode", -1) != 0:
            return SendResult(success=False, error=str(data.get("errmsg", data)))

        return SendResult(success=True, external_msg_id=str(data.get("msgid", uuid.uuid4().hex)))

    async def _send_via_webhook(self, payload: ReviewMessagePayload) -> SendResult:
        body = {"msgtype": "markdown", "markdown": {"content": payload.markdown}}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(settings.wecom_webhook_url, json=body)
            data = response.json()

        if data.get("errcode", 0) != 0:
            return SendResult(success=False, error=str(data.get("errmsg", data)), used_fallback=True)

        return SendResult(success=True, external_msg_id=f"webhook-{uuid.uuid4().hex[:12]}", used_fallback=True)

    async def _get_access_token(self) -> str | None:
        cache_key = settings.wecom_corp_id
        cached = _TOKEN_CACHE.get(cache_key)
        now = time.time()
        if cached and cached[1] > now:
            return cached[0]

        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        params = {"corpid": settings.wecom_corp_id, "corpsecret": settings.wecom_secret}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            data = response.json()

        if data.get("errcode", -1) != 0:
            logger.error("WeCom gettoken failed: %s", data)
            return None

        token = str(data["access_token"])
        expires_in = int(data.get("expires_in", 7200))
        _TOKEN_CACHE[cache_key] = (token, now + expires_in - 120)
        return token

    def verify_callback(self, *, msg_signature: str, timestamp: str, nonce: str, echo_str: str) -> bool:
        if not settings.wecom_callback_token:
            return False
        parts = sorted([settings.wecom_callback_token, timestamp, nonce, echo_str])
        digest = hashlib.sha1("".join(parts).encode()).hexdigest()
        return digest == msg_signature

    async def parse_callback_body(self, body: dict | str) -> InboundReply | None:
        if isinstance(body, str):
            content = body
            return InboundReply(raw_content=content)

        content = body.get("Content") or body.get("content")
        if not content:
            return None
        return InboundReply(
            raw_content=str(content),
            external_msg_id=str(body.get("MsgId") or body.get("msgid") or ""),
            responder=str(body.get("FromUserName") or body.get("from_user") or "") or None,
        )
