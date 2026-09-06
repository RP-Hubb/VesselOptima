"""
VesselOptima — Phase 11 Decision Governance & Institutional Control
Cryptographic Hashing & Tamper-Evident Audit Chain Engine
"""

import hashlib
import json
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional


def canonical_json_serializer(obj: Any) -> Any:
    """Helper serializer ensuring deterministic, order-independent JSON representation."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (int, float)):
        # Ensure clean float representation
        if isinstance(obj, float) and obj.is_integer():
            return int(obj)
        return round(obj, 6) if isinstance(obj, float) else obj
    raise TypeError(f"Type {type(obj)} not serializable in canonical JSON")


def compute_canonical_hash(payload: Any) -> str:
    """
    Computes a deterministic SHA-256 hex digest for any dictionary/list structure.
    Enforces sorted keys and uniform formatting.
    """
    encoded = json.dumps(
        payload,
        default=canonical_json_serializer,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compute_event_hash(
    sequence_number: int,
    event_type: str,
    actor: str,
    actor_role: str,
    action: str,
    description: str,
    previous_hash: str,
    metadata_payload: Optional[Dict[str, Any]] = None,
) -> str:
    """Computes tamper-evident SHA-256 hash for an individual audit chain link."""
    payload = {
        "sequence_number": sequence_number,
        "event_type": str(event_type),
        "actor": str(actor),
        "actor_role": str(actor_role),
        "action": str(action),
        "description": str(description),
        "previous_hash": str(previous_hash),
        "metadata_payload": metadata_payload or {},
    }
    return compute_canonical_hash(payload)


def compute_package_hash(package_dict: Dict[str, Any]) -> str:
    """
    Computes deterministic SHA-256 digest representing the complete immutable decision package.
    """
    core_fields = {
        "package_id": package_dict.get("package_id"),
        "version_number": package_dict.get("version_number", 1),
        "optimization_run_id": package_dict.get("optimization_run_id"),
        "scenario_run_id": package_dict.get("scenario_run_id"),
        "risk_run_id": package_dict.get("risk_run_id"),
        "decision_run_id": package_dict.get("decision_run_id"),
        "configuration_id": package_dict.get("configuration_id"),
        "configuration_version": package_dict.get("configuration_version", "1.0.0"),
        "recommendation_type": package_dict.get("recommendation_type"),
        "decision_score": package_dict.get("decision_score"),
        "confidence": package_dict.get("confidence"),
        "expected_contribution": package_dict.get("expected_contribution"),
        "risk_adjusted_contribution": package_dict.get("risk_adjusted_contribution"),
        "loss_probability": package_dict.get("loss_probability"),
        "cvar_95": package_dict.get("cvar_95"),
        "plan_reliability": package_dict.get("plan_reliability"),
        "input_hash": package_dict.get("input_hash"),
        "output_hash": package_dict.get("output_hash"),
    }
    return compute_canonical_hash(core_fields)


def verify_audit_chain(events: List[Any]) -> Dict[str, Any]:
    """
    Cryptographically verifies the append-only audit chain:
    1. Checks sequence continuity (1, 2, 3, ...).
    2. Event 1 must have previous_hash == 'GENESIS'.
    3. Event N must have previous_hash == Event N-1 hash.
    4. Recalculates event_hash for each event to ensure no in-place content tampering.
    """
    if not events:
        return {
            "is_valid": True,
            "status": "VALID",
            "event_count": 0,
            "verified_count": 0,
            "broken_links": 0,
            "first_broken_event": None,
            "failure_reason": None,
        }

    verified_count = 0

    for i, event in enumerate(events):
        seq = getattr(event, "sequence_number", None) or (event.get("sequence_number") if isinstance(event, dict) else None)
        event_id = getattr(event, "audit_event_id", None) or (event.get("audit_event_id") if isinstance(event, dict) else f"EVT-{i}")
        event_type = getattr(event, "event_type", None) or (event.get("event_type") if isinstance(event, dict) else "")
        actor = getattr(event, "actor", None) or (event.get("actor") if isinstance(event, dict) else "")
        actor_role = getattr(event, "actor_role", None) or (event.get("actor_role") if isinstance(event, dict) else "")
        action = getattr(event, "action", None) or (event.get("action") if isinstance(event, dict) else "")
        desc = getattr(event, "description", None) or (event.get("description") if isinstance(event, dict) else "")
        prev_hash = getattr(event, "previous_hash", None) or (event.get("previous_hash") if isinstance(event, dict) else "")
        recorded_hash = getattr(event, "event_hash", None) or (event.get("event_hash") if isinstance(event, dict) else "")
        metadata = getattr(event, "metadata_payload", None) or (event.get("metadata_payload") if isinstance(event, dict) else {})

        # 1. Sequence check
        if seq != i + 1:
            return {
                "is_valid": False,
                "status": "INVALID",
                "event_count": len(events),
                "verified_count": verified_count,
                "broken_links": 1,
                "first_broken_event": event_id,
                "failure_reason": f"Sequence out of order: expected {i+1}, found {seq}",
            }

        # 2. Previous hash check
        if i == 0:
            if prev_hash != "GENESIS":
                return {
                    "is_valid": False,
                    "status": "INVALID",
                    "event_count": len(events),
                    "verified_count": verified_count,
                    "broken_links": 1,
                    "first_broken_event": event_id,
                    "failure_reason": f"Genesis event previous_hash mismatch: expected 'GENESIS', found '{prev_hash}'",
                }
        else:
            prev_event = events[i - 1]
            expected_prev = getattr(prev_event, "event_hash", None) or (prev_event.get("event_hash") if isinstance(prev_event, dict) else "")
            if prev_hash != expected_prev:
                return {
                    "is_valid": False,
                    "status": "INVALID",
                    "event_count": len(events),
                    "verified_count": verified_count,
                    "broken_links": 1,
                    "first_broken_event": event_id,
                    "failure_reason": f"Hash chain broken at event {seq}: previous_hash does not match parent event hash",
                }

        # 3. Recompute hash check
        recalculated_hash = compute_event_hash(
            sequence_number=seq,
            event_type=event_type,
            actor=actor,
            actor_role=actor_role,
            action=action,
            description=desc,
            previous_hash=prev_hash,
            metadata_payload=metadata,
        )

        if recalculated_hash != recorded_hash:
            return {
                "is_valid": False,
                "status": "INVALID",
                "event_count": len(events),
                "verified_count": verified_count,
                "broken_links": 1,
                "first_broken_event": event_id,
                "failure_reason": f"Tamper detected in event {seq} content: recalculation mismatch",
            }

        verified_count += 1

    return {
        "is_valid": True,
        "status": "VALID",
        "event_count": len(events),
        "verified_count": verified_count,
        "broken_links": 0,
        "first_broken_event": None,
        "failure_reason": None,
    }
