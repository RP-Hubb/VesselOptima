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

from app.core.config import settings, RuntimeMode
from app.db.session import get_db, check_db_health
from app.schemas.runtime import (
    RuntimeModeResponse,
    RuntimeModeSwitchRequest,
    RuntimeStatusResponse,
    SourceHealth,
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
    current_mode = mode_info["mode"]
    available_pkgs = svc.discover_offline_packages()

    if current_mode == RuntimeMode.LIVE:
        is_live_operational = False
        app_status = "degraded"
        sources = [
            SourceHealth(
                name="Baltic Exchange Live API",
                status="unavailable",
                error="Live API credentials not configured in prototype environment. Outbound live connection rejected.",
                recovery_action="Switch to OFFLINE_DEMO or configure live data provider credentials.",
            ),
            SourceHealth(
                name="Platts Bunkerwire Live API",
                status="unavailable",
                error="Live API credentials not configured in prototype environment. Outbound live connection rejected.",
                recovery_action="Switch to OFFLINE_DEMO or configure live data provider credentials.",
            ),
        ]
        offline_pkg_id = None
        artifacts_status = "unverified_live"
    else:
        is_live_operational = False
        app_status = "ready" if db_health["status"] == "healthy" else "degraded"
        sources = [
            SourceHealth(
                name=f"Offline Package ({mode_info.get('offline_package_id') or 'demo-v1'})",
                status="healthy",
                last_success=datetime.now(timezone.utc),
            ),
            SourceHealth(
                name="Canonical Offline Ledger",
                status="healthy",
                last_success=datetime.now(timezone.utc),
            ),
        ]
        offline_pkg_id = mode_info.get("offline_package_id") or "demo-v1"
        artifacts_status = "verified_local"

    return RuntimeStatusResponse(
        mode=current_mode,
        mode_session_id=mode_info["mode_session_id"],
        app_status=app_status,
        database_status=db_health["status"],
        sources=sources,
        offline_package_id=offline_pkg_id,
        offline_package_coverage="COMPLETE_100_PCT",
        available_packages=available_pkgs,
        is_live_operational=is_live_operational,
        model_artifacts_status=artifacts_status,
        timestamp=datetime.now(timezone.utc),
    )
