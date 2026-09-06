"""
VesselOptima — Phase 12 Maritime Data Integration & Quality Governance
Cryptographic SHA-256 Dataset and Record Hashing
"""

import hashlib
import json
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List


def canonical_json_serializer(obj: Any) -> Any:
    """Deterministic, order-invariant serializer for JSON structures."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, float):
        if obj.is_integer():
            return int(obj)
        return round(obj, 6)
    raise TypeError(f"Type {type(obj)} not serializable in canonical JSON")


def compute_canonical_hash(payload: Any) -> str:
    """Computes a deterministic SHA-256 hex digest for any dictionary/list structure."""
    encoded = json.dumps(
        payload,
        default=canonical_json_serializer,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compute_record_hash(record_dict: Dict[str, Any]) -> str:
    """Computes deterministic SHA-256 digest for an individual record."""
    # Filter out runtime temporary keys
    clean_dict = {k: v for k, v in record_dict.items() if not k.startswith("_")}
    return compute_canonical_hash(clean_dict)


def compute_dataset_hash(
    records: List[Dict[str, Any]],
    dataset_type: str,
    version_number: int = 1,
) -> str:
    """
    Computes a deterministic SHA-256 content hash representing the complete dataset.
    Hashes sorted record digests to ensure invariance to record row order if re-indexed.
    """
    record_hashes = [compute_record_hash(r) for r in records]
    record_hashes.sort()

    manifest = {
        "dataset_type": str(dataset_type),
        "version_number": version_number,
        "record_count": len(records),
        "record_hashes_root": compute_canonical_hash(record_hashes),
    }
    return compute_canonical_hash(manifest)


def verify_dataset_integrity(
    records: List[Dict[str, Any]],
    dataset_type: str,
    version_number: int,
    expected_hash: str,
) -> bool:
    """Verifies that records hash matches expected SHA-256 digest exactly."""
    calculated = compute_dataset_hash(records, dataset_type, version_number)
    return calculated == expected_hash
