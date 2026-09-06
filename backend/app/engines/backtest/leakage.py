"""
VesselOptima — Phase 13: Information Leakage & Look-Ahead Bias Detector

Enforces the absolute temporal integrity of the backtesting engine.
Guarantees that no future information can contaminate historical decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.engines.backtest.reason_codes import LeakageCode


@dataclass
class LeakageViolation:
    """Individual record of detected temporal or provenance leakage."""
    leakage_type: LeakageCode
    severity: str  # CRITICAL, WARNING
    field_name: str
    decision_timestamp: datetime
    information_timestamp: Optional[datetime]
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "leakage_type": self.leakage_type.value if hasattr(self.leakage_type, "value") else str(self.leakage_type),
            "severity": self.severity,
            "field_name": self.field_name,
            "decision_timestamp": self.decision_timestamp.isoformat(),
            "information_timestamp": self.information_timestamp.isoformat() if self.information_timestamp else None,
            "details": self.details,
        }


@dataclass
class LeakageReport:
    """Aggregated leakage assessment for a backtest step or full run."""
    is_valid: bool
    violations: List[LeakageViolation] = field(default_factory=list)
    checked_records_count: int = 0
    clean_records_count: int = 0

    @property
    def has_critical_leakage(self) -> bool:
        return any(v.severity == "CRITICAL" for v in self.violations)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid and not self.has_critical_leakage,
            "has_critical_leakage": self.has_critical_leakage,
            "total_violations": len(self.violations),
            "checked_records_count": self.checked_records_count,
            "clean_records_count": self.clean_records_count,
            "violations": [v.to_dict() for v in self.violations],
        }


class InformationLeakageDetector:
    """
    Validates point-in-time constraints across all inputs fed to the decision pipeline.
    """
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def inspect_observation(
        self,
        decision_timestamp: datetime,
        information_timestamp: Optional[datetime],
        availability_timestamp: Optional[datetime],
        field_name: str,
        source_dataset_version: Optional[int] = None,
        max_allowed_version: Optional[int] = None,
        is_current_live_data: bool = False,
    ) -> Optional[LeakageViolation]:
        """
        Validates a single data item against the decision horizon.
        """
        # 1. Check for live/current dataset usage
        if is_current_live_data:
            return LeakageViolation(
                leakage_type=LeakageCode.CURRENT_DATASET_USED,
                severity="CRITICAL",
                field_name=field_name,
                decision_timestamp=decision_timestamp,
                information_timestamp=information_timestamp,
                details={"reason": "Decision pipeline accessed active/current mutable dataset instead of historical freeze."},
            )

        # 2. Check for future dataset version
        if (
            source_dataset_version is not None
            and max_allowed_version is not None
            and source_dataset_version > max_allowed_version
        ):
            return LeakageViolation(
                leakage_type=LeakageCode.FUTURE_DATASET_VERSION_USED,
                severity="CRITICAL",
                field_name=field_name,
                decision_timestamp=decision_timestamp,
                information_timestamp=information_timestamp,
                details={
                    "version_used": source_dataset_version,
                    "max_allowed": max_allowed_version,
                },
            )

        # 3. Check for missing / ambiguous availability timestamp
        effective_avail = availability_timestamp or information_timestamp
        if effective_avail is None:
            return LeakageViolation(
                leakage_type=LeakageCode.POINT_IN_TIME_UNCERTAIN,
                severity="CRITICAL" if self.strict_mode else "WARNING",
                field_name=field_name,
                decision_timestamp=decision_timestamp,
                information_timestamp=None,
                details={"reason": "Availability timestamp cannot be established for decision-critical variable."},
            )

        # 4. Critical Look-Ahead Detection: information became available after decision time
        if effective_avail > decision_timestamp:
            return LeakageViolation(
                leakage_type=LeakageCode.LOOKAHEAD_BIAS_DETECTED,
                severity="CRITICAL",
                field_name=field_name,
                decision_timestamp=decision_timestamp,
                information_timestamp=effective_avail,
                details={
                    "delta_seconds": (effective_avail - decision_timestamp).total_seconds(),
                    "reason": f"Variable became available at {effective_avail.isoformat()}, after decision at {decision_timestamp.isoformat()}.",
                },
            )

        # 5. Future data used: event timestamp strictly in the future
        if information_timestamp and information_timestamp > decision_timestamp:
            return LeakageViolation(
                leakage_type=LeakageCode.FUTURE_DATA_USED,
                severity="CRITICAL",
                field_name=field_name,
                decision_timestamp=decision_timestamp,
                information_timestamp=information_timestamp,
                details={"reason": "Observation event timestamp is strictly ahead of historical decision horizon."},
            )

        return None

    def validate_snapshot_inputs(
        self,
        decision_timestamp: datetime,
        input_records: List[Dict[str, Any]],
        max_allowed_version: Optional[int] = None,
    ) -> LeakageReport:
        """
        Batch inspects all records feeding into a snapshot or decision step.
        """
        violations: List[LeakageViolation] = []
        clean_count = 0

        for rec in input_records:
            info_ts = rec.get("information_timestamp") or rec.get("event_timestamp")
            avail_ts = rec.get("availability_timestamp")
            field_name = rec.get("field_name", rec.get("entity_id", "unknown_field"))
            version = rec.get("source_dataset_version")
            is_live = rec.get("is_live", False)

            violation = self.inspect_observation(
                decision_timestamp=decision_timestamp,
                information_timestamp=info_ts,
                availability_timestamp=avail_ts,
                field_name=field_name,
                source_dataset_version=version,
                max_allowed_version=max_allowed_version,
                is_current_live_data=is_live,
            )

            if violation:
                violations.append(violation)
            else:
                clean_count += 1

        is_valid = len(violations) == 0
        return LeakageReport(
            is_valid=is_valid,
            violations=violations,
            checked_records_count=len(input_records),
            clean_records_count=clean_count,
        )
