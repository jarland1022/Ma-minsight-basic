"""Privacy disclosure and policy status API (P0-06-A/D)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_async_session
from app.privacy.config import ensure_privacy_config_keys, load_privacy_policy
from app.privacy.disclosure import build_data_flow_disclosure

router = APIRouter(prefix="/api/v1/privacy", tags=["privacy"])


@router.get("/disclosure", dependencies=[Depends(require_admin)])
async def get_privacy_disclosure(
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Admin-facing data-flow disclosure. Does not claim air-gap."""
    await ensure_privacy_config_keys(session)
    await session.commit()
    policy = await load_privacy_policy(session)
    return build_data_flow_disclosure(policy)


@router.get("/policy", dependencies=[Depends(require_admin)])
async def get_privacy_policy_status(
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Backend-enforced channel switches (no secrets)."""
    await ensure_privacy_config_keys(session)
    await session.commit()
    policy = await load_privacy_policy(session)
    return {
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "strict_mode": policy.strict_mode,
        "channels": {
            "llm": policy.llm_egress_enabled,
            "ti": policy.ti_egress_enabled,
            "wecom": policy.wecom_egress_enabled,
            "embed": policy.embed_egress_enabled,
            "webhook": policy.webhook_egress_enabled,
        },
        "field_allow": {
            "public_ip_plaintext": policy.allow_public_ip_plaintext,
            "username_plaintext": policy.allow_username_plaintext,
            "hostname_plaintext": policy.allow_hostname_plaintext,
            "full_url": policy.allow_full_url,
            "wecom_host_user": policy.wecom_allow_host_user,
        },
        "allowed_llm_base_urls": policy.allowed_llm_base_urls,
        "pseudonym_secret_configured": policy.pseudonym_secret is not None,
        "note": "Pseudonymization is not anonymization. Frontend cannot override these switches.",
    }
