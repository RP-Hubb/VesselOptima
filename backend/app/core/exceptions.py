"""
VesselOptima — Exception Handling

Structured error responses for the API.
Raw stack traces are kept in server logs, never exposed to API clients.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any, List, Optional


# ── Error response schema ────────────────────────────────────────────

class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[List[ErrorDetail]] = None
    trace_id: Optional[str] = None
    recovery_actions: Optional[List[str]] = None


# ── Custom exceptions ────────────────────────────────────────────────

class VesselOptimaError(Exception):
    """Base exception for all VesselOptima application errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 500,
        details: Optional[List[ErrorDetail]] = None,
        recovery_actions: Optional[List[str]] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        self.recovery_actions = recovery_actions
        super().__init__(message)


class InvalidRuntimeModeError(VesselOptimaError):
    def __init__(self, mode: str):
        super().__init__(
            code="INVALID_RUNTIME_MODE",
            message=f"Invalid runtime mode '{mode}'. Only 'LIVE' and 'OFFLINE_DEMO' are permitted.",
            status_code=422,
            recovery_actions=["Set RUNTIME_MODE to 'LIVE' or 'OFFLINE_DEMO'"],
        )


class DatabaseUnavailableError(VesselOptimaError):
    def __init__(self, detail: str = ""):
        super().__init__(
            code="DATABASE_UNAVAILABLE",
            message=f"Database is unavailable. {detail}".strip(),
            status_code=503,
            recovery_actions=["Check database connection", "Verify DATABASE_URL"],
        )


class LiveSourceUnavailableError(VesselOptimaError):
    def __init__(self, source: str):
        super().__init__(
            code="LIVE_SOURCE_UNAVAILABLE",
            message=f"Live data source '{source}' is unavailable.",
            status_code=503,
            recovery_actions=[
                "Check source connectivity",
                "Verify source credentials",
                "Do NOT switch to OFFLINE_DEMO automatically",
            ],
        )


class OfflineNetworkProhibitedError(VesselOptimaError):
    def __init__(self):
        super().__init__(
            code="OFFLINE_NETWORK_PROHIBITED",
            message="External network access is prohibited in OFFLINE_DEMO mode.",
            status_code=403,
            recovery_actions=["Switch to LIVE mode to access external sources"],
        )


class ValidationError(VesselOptimaError):
    def __init__(self, details: List[ErrorDetail]):
        super().__init__(
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            status_code=422,
            details=details,
        )


# ── Exception handlers ───────────────────────────────────────────────

async def vesseloptima_exception_handler(
    request: Request, exc: VesselOptimaError
) -> JSONResponse:
    """Handle VesselOptima application exceptions with structured responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            recovery_actions=exc.recovery_actions,
        ).model_dump(exclude_none=True),
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Catch-all for unhandled exceptions.
    Log the full traceback server-side but return only a safe message to clients.
    """
    from app.core.logging import get_logger
    logger = get_logger("exceptions")
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            code="INTERNAL_ERROR",
            message="An internal error occurred. Check server logs for details.",
        ).model_dump(exclude_none=True),
    )
