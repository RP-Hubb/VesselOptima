"""
VesselOptima — FastAPI Application Entry Point

Thin orchestration layer. Domain services remain pure Python modules.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import (
    VesselOptimaError,
    vesseloptima_exception_handler,
    unhandled_exception_handler,
)
from app.db.base import Base
from app.db.session import engine
from app.api.v1 import data, forecast, health, runtime



# Import models so they are registered with Base.metadata
import app.models  # noqa: F401

logger = get_logger("main")


# ── Lifespan ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("=" * 60)
    logger.info("VesselOptima starting")
    logger.info(f"  Runtime mode : {settings.runtime_mode.value}")
    logger.info(f"  Environment  : {settings.app_env.value}")
    logger.info(f"  Log level    : {settings.log_level}")
    logger.info(f"  Database     : {'SQLite' if 'sqlite' in settings.database_url else 'PostgreSQL'}")
    logger.info("=" * 60)

    # Create tables (for dev/SQLite; production uses Alembic migrations)
    if "sqlite" in settings.database_url:
        Base.metadata.create_all(bind=engine)
        logger.info("SQLite tables created/verified")

    yield

    logger.info("VesselOptima shutting down")


# ── Application ──────────────────────────────────────────────────────

app = FastAPI(
    title="VesselOptima API",
    description=(
        "Freight intelligence, chartering feasibility, and procurement "
        "optimization platform for bulk-cargo logistics. SIH26006."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception handlers ───────────────────────────────────────────────

app.add_exception_handler(VesselOptimaError, vesseloptima_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# ── Mode header middleware ───────────────────────────────────────────

@app.middleware("http")
async def add_mode_headers(request: Request, call_next):
    """
    Per Build Spec: every API response includes runtime mode headers.
    X-VesselOptima-Mode and X-Data-Context-ID.
    """
    response = await call_next(request)
    response.headers["X-VesselOptima-Mode"] = settings.runtime_mode.value
    # data_context_id will be fully resolved in later phases
    response.headers["X-Data-Context-ID"] = (
        "offline-demo-context"
        if settings.runtime_mode.value == "OFFLINE_DEMO"
        else "live-context"
    )
    return response

# ── Routes ───────────────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(runtime.router, prefix="/v1")
app.include_router(data.router, prefix="/v1")
app.include_router(forecast.router, prefix="/v1")




@app.get("/", tags=["Root"])
def root():
    """API root — confirms the application is alive."""
    return {
        "app": "VesselOptima",
        "version": "1.0.0",
        "mode": settings.runtime_mode.value,
        "status": "running",
    }
