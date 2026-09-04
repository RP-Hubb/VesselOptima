"""
VesselOptima — Pydantic Schemas: Common

Shared response structures.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""
    status: str  # healthy, degraded, unhealthy
    database: str
    runtime_mode: str
    timestamp: datetime
    version: str = "1.0.0"
    detail: Optional[str] = None
