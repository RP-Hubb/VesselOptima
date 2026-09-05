"""
VesselOptima — Core Configuration

Centralized, validated configuration via pydantic-settings.
All environment-specific values are loaded from .env or environment variables.
No secrets are hardcoded.
"""

from __future__ import annotations

import enum
import json
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings


class RuntimeMode(str, enum.Enum):
    """
    VesselOptima supports exactly two explicit modes.
    There is no third mode, no hybrid mode, and no automatic fallback.
    """
    LIVE = "LIVE"
    OFFLINE_DEMO = "OFFLINE_DEMO"


class AppEnvironment(str, enum.Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    # ── Runtime mode ─────────────────────────────────────────────
    runtime_mode: RuntimeMode = RuntimeMode.OFFLINE_DEMO

    # ── Database ─────────────────────────────────────────────────
    database_url: str = "sqlite:///./vesseloptima.db"

    # ── Application ──────────────────────────────────────────────
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_env: AppEnvironment = AppEnvironment.DEVELOPMENT
    log_level: str = "INFO"

    # ── CORS ─────────────────────────────────────────────────────
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # ── Offline package ──────────────────────────────────────────
    offline_package_dir: str = "../data/offline/packages"

    # ── Model artifacts ──────────────────────────────────────────
    model_artifacts_dir: str = "../models"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [s.strip() for s in v.split(",")]
        return v

    @field_validator("runtime_mode", mode="before")
    @classmethod
    def validate_runtime_mode(cls, v):
        """Reject any value that is not exactly LIVE or OFFLINE_DEMO."""
        if isinstance(v, str):
            v = v.strip().upper()
            if v not in ("LIVE", "OFFLINE_DEMO"):
                raise ValueError(
                    f"Invalid RUNTIME_MODE '{v}'. "
                    "Only 'LIVE' and 'OFFLINE_DEMO' are permitted. "
                    "There is no hybrid, fallback, or third mode."
                )
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Singleton — import this everywhere
settings = Settings()
