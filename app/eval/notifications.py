"""Failure notifications for eval runs (via EgressGateway)."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.eval.config import load_eval_config
from app.privacy.egress_gateway import EgressDeniedError, get_egress_gateway
from app.privacy.types import ContentType, EgressChannel, EgressContext

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
    gateway = get_egress_gateway()
    try:
        await gateway.send(
            channel=EgressChannel.WEBHOOK,
            method="POST",
            url=str(url),
            json_body=payload,
            content_type=ContentType.JSON,
            context=EgressContext(),
            session=session,
            timeout=10.0,
        )
    except EgressDeniedError as exc:
        logger.warning("Eval webhook egress denied: %s", exc.reason)
    except Exception:
        logger.exception("Failed to send eval failure webhook")
