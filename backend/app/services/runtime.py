"""
VesselOptima — Runtime Service

Business logic for runtime mode management.
Enforces the two-mode contract: LIVE and OFFLINE_DEMO only.
No hybrid mode, no automatic fallback.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings, RuntimeMode
from app.core.logging import get_logger
from app.core.exceptions import InvalidRuntimeModeError
from app.models.domain import RuntimeModeEvent, RuntimeModeEnum

logger = get_logger("services.runtime")


class RuntimeService:
    """Manages runtime mode state and transitions."""

    def __init__(self, db: Session):
        self.db = db

    def get_current_mode(self) -> dict:
        """
        Get the current runtime mode.
        Returns the most recent mode event, or the configured default.
        """
        event = (
            self.db.query(RuntimeModeEvent)
            .order_by(RuntimeModeEvent.selected_at.desc())
            .first()
        )

        if event:
            return {
                "mode": RuntimeMode(event.mode.value),
                "mode_session_id": event.mode_session_id,
                "selected_at": event.selected_at,
                "data_context_id": self._resolve_data_context(RuntimeMode(event.mode.value)),
                "offline_package_id": self._resolve_offline_package_id(RuntimeMode(event.mode.value)),
            }

        # No mode event yet — use the configured default
        return {
            "mode": settings.runtime_mode,
            "mode_session_id": "initial-" + str(uuid.uuid4())[:8],
            "selected_at": datetime.now(timezone.utc),
            "data_context_id": self._resolve_data_context(settings.runtime_mode),
            "offline_package_id": self._resolve_offline_package_id(settings.runtime_mode),
        }

    def switch_mode(self, mode: RuntimeMode, reason: str | None = None, actor: str = "system") -> dict:
        """
        Switch runtime mode. Creates an audit event.
        This is an explicit, authorized action — never automatic.
        """
        session_id = str(uuid.uuid4())

        event = RuntimeModeEvent(
            mode=RuntimeModeEnum(mode.value),
            mode_session_id=session_id,
            actor=actor,
            selected_at=datetime.now(timezone.utc),
            reason=reason,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        logger.info(f"Runtime mode switched to {mode.value} (session: {session_id})")

        return {
            "mode": mode,
            "mode_session_id": session_id,
            "selected_at": event.selected_at,
            "data_context_id": self._resolve_data_context(mode),
            "offline_package_id": self._resolve_offline_package_id(mode),
        }

    def _resolve_data_context(self, mode: RuntimeMode) -> str:
        """
        Resolve the data context ID based on mode.
        In OFFLINE_DEMO, this is the package ID.
        In LIVE, this is a live context identifier.
        """
        if mode == RuntimeMode.OFFLINE_DEMO:
            return "offline-demo-context"
        return "live-context"

    def _resolve_offline_package_id(self, mode: RuntimeMode) -> str | None:
        """Only return a package ID in OFFLINE_DEMO mode."""
        if mode == RuntimeMode.OFFLINE_DEMO:
            # Phase 2 will implement actual package lookup
            return None
        return None
