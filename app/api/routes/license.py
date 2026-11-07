"""License status API for the Professional (AI-SEC) deployment.

This stack ships as Pro by default — import/gating lives in the Community
edition (Ma-minsight-basic). Endpoints here keep the console License page working.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.audit_helpers import soft_security_audit
from app.api.deps import require_admin, require_auth
from app.db.session import get_async_session
from app.services.audit import AuditResult
from app.services.auth import AuthContext

router = APIRouter(prefix="/api/v1/license", tags=["license"])


@router.get("/status", dependencies=[Depends(require_auth)])
async def license_status() -> dict:
    return {
        "edition": "professional",
        "pro_enabled": True,
        "license": {
            "status": "active",
            "hint": "This deployment is MA-MinSight Professional (AI-SEC). No .lic import is required.",
            "client_name": "local-pro",
        },
    }


@router.get("/fingerprint", dependencies=[Depends(require_auth)])
async def license_fingerprint() -> dict:
    return {
        "fingerprint": "professional-build-no-fingerprint",
        "source": "ai-sec",
        "hint": "Fingerprint/import applies to Community Edition upgrades only.",
    }


@router.post("/import")
async def license_import(
    request: Request,
    auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    await soft_security_audit(
        session,
        request,
        auth,
        action="license.import",
        resource_type="license",
        resource_id="import",
        detail={"edition": "professional", "accepted": False},
        result=AuditResult.DENIED,
        commit=True,
    )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="This Professional deployment does not import Community license.lic files.",
    )
