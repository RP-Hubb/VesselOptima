"""
VesselOptima — Health Endpoints

GET /health and GET /v1/health
Distinguishes between application alive, database available, and runtime config valid.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import settings
from app.db.session import check_db_health
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Root health check — application alive + database + runtime config."""
    db_health = check_db_health()
    db_ok = db_health["status"] == "healthy"

    overall = "healthy" if db_ok else "degraded"

    return HealthResponse(
        status=overall,
        database=db_health["status"],
        runtime_mode=settings.runtime_mode.value,
        timestamp=datetime.now(timezone.utc),
        detail=None if db_ok else db_health["detail"],
    )


@router.get("/v1/health", response_model=HealthResponse)
def health_check_v1():
    """Versioned health check — same logic."""
    return health_check()
