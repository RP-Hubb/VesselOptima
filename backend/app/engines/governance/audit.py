"""
VesselOptima — Phase 11 Decision Governance & Institutional Control
Append-Only, Hash-Chained Audit Trail Service
"""

from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.engines.governance.hashing import (
    compute_event_hash,
    verify_audit_chain,
)
from app.engines.governance.models import AuditChainVerificationResult
from app.engines.governance.reason_codes import AuditEventType


def build_audit_event(
    sequence_number: int,
    event_type: AuditEventType | str,
    actor: str,
    actor_role: str,
    action: str,
    description: str,
    previous_hash: str,
    metadata_payload: Optional[Dict[str, Any]] = None,
    audit_event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Constructs a single tamper-evident audit chain link.
    """
    evt_id = audit_event_id or f"AUDIT-{sequence_number:04d}-{uuid4().hex[:6].upper()}"
    evt_type_str = event_type.value if isinstance(event_type, AuditEventType) else str(event_type)

    evt_hash = compute_event_hash(
        sequence_number=sequence_number,
        event_type=evt_type_str,
        actor=actor,
        actor_role=actor_role,
        action=action,
        description=description,
        previous_hash=previous_hash,
        metadata_payload=metadata_payload or {},
    )

    return {
        "audit_event_id": evt_id,
        "sequence_number": sequence_number,
        "event_type": evt_type_str,
        "actor": actor,
        "actor_role": actor_role,
        "action": action,
        "description": description,
        "previous_hash": previous_hash,
        "event_hash": evt_hash,
        "metadata_payload": metadata_payload or {},
    }


def verify_package_audit_trail(events: List[Any]) -> AuditChainVerificationResult:
    """
    Cryptographically verifies the continuity and immutability of an audit chain.
    """
    diag = verify_audit_chain(events)
    return AuditChainVerificationResult(
        is_valid=diag["is_valid"],
        status=diag["status"],
        event_count=diag["event_count"],
        verified_count=diag["verified_count"],
        broken_links=diag["broken_links"],
        first_broken_event=diag["first_broken_event"],
        failure_reason=diag["failure_reason"],
    )
