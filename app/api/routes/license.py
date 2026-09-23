"""License status, fingerprint, and import API."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import require_admin, require_auth
from app.license import get_manager, read_edition

router = APIRouter(prefix="/api/v1/license", tags=["license"])


@router.get("/status", dependencies=[Depends(require_auth)])
async def license_status() -> dict:
    mgr = get_manager()
    return {
        "edition": read_edition(),
        "pro_enabled": mgr.allow_operation(),
        "license": mgr.status().to_dict(),
    }


@router.get("/fingerprint", dependencies=[Depends(require_auth)])
async def license_fingerprint() -> dict:
    mgr = get_manager()
    try:
        return mgr.fingerprint_detail()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/import", dependencies=[Depends(require_admin)])
async def license_import(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请上传 .lic 文件（字段名 file）",
        )

    mgr = get_manager()
    suffix = Path(file.filename).suffix or ".lic"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        mgr.import_file(tmp_path)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return {
        "success": True,
        "message": "License 导入成功",
        "license": mgr.status().to_dict(),
    }
