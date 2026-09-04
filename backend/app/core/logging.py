"""
VesselOptima — Structured Logging

Provides a consistent logger for the application.
Logs are written to stdout with structured format suitable for both
development and production. Secrets and credentials are never logged.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from app.core.config import settings


class StructuredFormatter(logging.Formatter):
    """Compact structured log format: timestamp | level | module | message"""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        level = record.levelname.ljust(8)
        module = record.name
        message = record.getMessage()

        base = f"{timestamp} | {level} | {module} | {message}"

        if record.exc_info and record.exc_info[0] is not None:
            exc_text = self.formatException(record.exc_info)
            base += f"\n{exc_text}"

        return base


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger for the given module name."""
    logger = logging.getLogger(f"vesseloptima.{name}")

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)

    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    logger.propagate = False
    return logger
