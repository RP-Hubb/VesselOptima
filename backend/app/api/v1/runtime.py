"""
VesselOptima — Runtime Mode Endpoints

GET  /v1/runtime/mode    — current mode
PUT  /v1/runtime/mode    — switch mode (explicit, audited)
GET  /v1/runtime/status  — source/package/artifact health

Per Build Spec: the runtime enum and API accept only LIVE and OFFLINE_DEMO.
No other state is representable.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db, check_db_health
from app.schemas.runtime import (
    RuntimeModeResponse,
    RuntimeModeSwitchRequest,
    RuntimeStatusResponse,
)
from app.services.runtime import RuntimeService

router = APIRouter(prefix="/runtime", tags=["Runtime"])


@router.get("/mode", response_model=RuntimeModeResponse)
def get_current_mode(db: Session = Depends(get_db)):
    """Return the current explicit runtime mode."""
    svc = RuntimeService(db)
    result = svc.get_current_mode()
    return RuntimeModeResponse(**result)


@router.put("/mode", response_model=RuntimeModeResponse)
def switch_mode(req: RuntimeModeSwitchRequest, db: Session = Depends(get_db)):
    """
    Switch runtime mode. Requires explicit confirmation.
    Rejects any mode that is not LIVE or OFFLINE_DEMO.
    """
    if not req.confirmation:
        raise HTTPException(
            status_code=400,
            detail="Mode switch requires explicit confirmation. Set confirmation=true.",
        )

    svc = RuntimeService(db)
    result = svc.switch_mode(mode=req.mode, reason=req.reason)
    return RuntimeModeResponse(**result)


@router.get("/status", response_model=RuntimeStatusResponse)
def get_runtime_status(db: Session = Depends(get_db)):
    """
    Runtime status including source health, package info, and artifact status.
    Makes the active mode explicit — never hides it.
    """
    svc = RuntimeService(db)
    mode_info = svc.get_current_mode()
    db_health = check_db_health()

    app_status = "ready" if db_health["status"] == "healthy" else "degraded"

    return RuntimeStatusResponse(
        mode=mode_info["mode"],
        mode_session_id=mode_info["mode_session_id"],
        app_status=app_status,
        database_status=db_health["status"],
        sources=[],  # Phase 2: data source health will be populated
        offline_package_id=mode_info.get("offline_package_id"),
        offline_package_coverage=None,  # Phase 2
        model_artifacts_status=None,  # Phase 3
        timestamp=datetime.now(timezone.utc),
    )
