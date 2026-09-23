"""Failure notifications for eval runs."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.eval.config import load_eval_config

logger = logging.getLogger(__name__)


async def notify_eval_failure(session: AsyncSession, *, title: str, detail: str) -> None:
    config = await load_eval_config(session)
    url = config.alert_webhook_url
    if not url:
        return
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": f"**{title}**\n{detail}"},
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=payload)
    except Exception:
        logger.exception("Failed to send eval failure webhook")
