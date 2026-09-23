"""Defensive investigation playbook catalog API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_auth
from app.playbooks.loader import catalog_meta, get_playbook, list_playbooks, match_playbooks

router = APIRouter(prefix="/api/v1/playbooks", tags=["playbooks"])


@router.get("", dependencies=[Depends(require_auth)])
async def list_playbooks_api(
    category: str | None = None,
    domain: str | None = None,
) -> dict:
    meta = catalog_meta()
    return {
        **meta,
        "items": list_playbooks(category=category, domain=domain),
    }


@router.get("/match", dependencies=[Depends(require_auth)])
async def match_playbooks_api(
    category: str = Query(..., min_length=1),
    limit: int = Query(default=3, ge=1, le=10),
) -> dict:
    return {"category": category, "items": match_playbooks(category, limit=limit)}


@router.get("/{playbook_id}", dependencies=[Depends(require_auth)])
async def get_playbook_api(playbook_id: str) -> dict:
    item = get_playbook(playbook_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook not found")
    return item
