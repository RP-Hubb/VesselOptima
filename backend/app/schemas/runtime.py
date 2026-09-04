"""
VesselOptima — Pydantic Schemas: Runtime

API request/response schemas for runtime mode and status endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator

from app.core.config import RuntimeMode


class RuntimeModeResponse(BaseModel):
    """GET /v1/runtime/mode response."""
    mode: RuntimeMode
    mode_session_id: str
    selected_at: datetime
    data_context_id: Optional[str] = None
    offline_package_id: Optional[str] = None

    model_config = {"from_attributes": True}


class RuntimeModeSwitchRequest(BaseModel):
    """PUT /v1/runtime/mode request."""
    mode: RuntimeMode
    confirmation: bool
    reason: Optional[str] = None

    @field_validator("mode", mode="before")
    @classmethod
    def validate_mode(cls, v):
        if isinstance(v, str):
            v = v.strip().upper()
            if v not in ("LIVE", "OFFLINE_DEMO"):
                raise ValueError(
                    f"Invalid mode '{v}'. Only 'LIVE' and 'OFFLINE_DEMO' are accepted."
                )
        return v


class SourceHealth(BaseModel):
    """Individual data source health status."""
    name: str
    status: str  # healthy, stale, unavailable, unknown
    last_success: Optional[datetime] = None
    error: Optional[str] = None
    recovery_action: Optional[str] = None


class RuntimeStatusResponse(BaseModel):
    """GET /v1/runtime/status response."""
    mode: RuntimeMode
    mode_session_id: Optional[str] = None
    app_status: str  # ready, degraded, error
    database_status: str
    sources: List[SourceHealth] = []
    offline_package_id: Optional[str] = None
    offline_package_coverage: Optional[str] = None
    model_artifacts_status: Optional[str] = None
    timestamp: datetime
