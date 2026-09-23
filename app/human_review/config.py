"""Human review configuration."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_config import get_config_bool, get_config_int, get_config_value


@dataclass
class HumanReviewConfig:
    enabled: bool = True
    channel: str = "wecom"
    poll_interval_minutes: int = 2
    batch_size: int = 10
    timeout_hours: int = 24
    max_resend: int = 2
    reinvestigation_enabled: bool = True
    reinvestigation_counts_budget: bool = False
    wecom_to_user: str = "@all"
    message_max_chars: int = 1800
    audit_sample_enabled: bool = True
    audit_sample_notify_via_im: bool = False


async def load_human_review_config(session: AsyncSession) -> HumanReviewConfig:
    to_user_raw = await get_config_value(session, "human_review.wecom_to_user", "@all")
    if isinstance(to_user_raw, dict) and "value" in to_user_raw:
        wecom_to_user = str(to_user_raw["value"])
    elif isinstance(to_user_raw, str):
        wecom_to_user = to_user_raw
    else:
        wecom_to_user = "@all"

    channel_raw = await get_config_value(session, "human_review.channel", "wecom")
    if isinstance(channel_raw, dict) and "value" in channel_raw:
        channel = str(channel_raw["value"])
    elif isinstance(channel_raw, str):
        channel = channel_raw
    else:
        channel = "wecom"

    return HumanReviewConfig(
        enabled=await get_config_bool(session, "human_review.enabled", True),
        channel=channel,
        poll_interval_minutes=await get_config_int(session, "human_review.poll_interval_minutes", 2),
        batch_size=await get_config_int(session, "human_review.batch_size", 10),
        timeout_hours=await get_config_int(session, "human_review.timeout_hours", 24),
        max_resend=await get_config_int(session, "human_review.max_resend", 2),
        reinvestigation_enabled=await get_config_bool(session, "human_review.reinvestigation_enabled", True),
        reinvestigation_counts_budget=await get_config_bool(
            session, "human_review.reinvestigation_counts_budget", False
        ),
        wecom_to_user=wecom_to_user,
        message_max_chars=await get_config_int(session, "human_review.message_max_chars", 1800),
        audit_sample_enabled=await get_config_bool(session, "audit_sample.enabled", True),
        audit_sample_notify_via_im=await get_config_bool(session, "audit_sample.notify_via_im", False),
    )


async def ensure_human_review_defaults(session: AsyncSession) -> None:
    from app.services.system_config import ensure_config_key

    defaults = [
        ("human_review.enabled", {"value": True}, "Enable IM human review dispatch"),
        ("human_review.channel", {"value": "wecom"}, "IM channel adapter type"),
        ("human_review.poll_interval_minutes", {"value": 2}, "Human review scheduler interval"),
        ("human_review.batch_size", {"value": 10}, "Max review requests sent per run"),
        ("human_review.timeout_hours", {"value": 24}, "Hours before sent request expires"),
        ("human_review.max_resend", {"value": 2}, "Max resends after expiry per event"),
        ("human_review.reinvestigation_enabled", {"value": True}, "Re-run Agent after human reply"),
        (
            "human_review.reinvestigation_counts_budget",
            {"value": False},
            "Whether reinvestigation counts toward daily budget",
        ),
        ("human_review.wecom_to_user", {"value": "@all"}, "WeCom recipient userid"),
        ("human_review.message_max_chars", {"value": 1800}, "Max outbound markdown length"),
        ("audit_sample.enabled", {"value": True}, "Enable audit sample generation"),
        ("audit_sample.notify_via_im", {"value": False}, "Push audit samples via IM"),
    ]
    for key, value, description in defaults:
        await ensure_config_key(session, key, value, description)
