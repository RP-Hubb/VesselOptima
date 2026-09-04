"""
VesselOptima — Database Connection & Session Management

Uses SQLAlchemy 2.0 style with sessionmaker dependency injection.
Supports both SQLite (development) and PostgreSQL (production).
"""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("db.session")

# ── Engine creation ──────────────────────────────────────────────────

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

logger.info(f"Database engine created: {settings.database_url.split('@')[-1] if '@' in settings.database_url else settings.database_url}")


# ── Dependency injection ─────────────────────────────────────────────

def get_db() -> Session:
    """FastAPI dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_health() -> dict:
    """
    Check database connectivity.
    Returns a dict with status and detail.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "detail": "Database connection successful"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "detail": str(e)}
