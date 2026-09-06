"""
VesselOptima — Phase 12 Maritime Data Integration & Quality Governance
Dataset Versioning & Granular Differential Comparison Engine
"""

from typing import Any, Dict, List, Set, Tuple

from app.engines.data.hashing import compute_record_hash
from app.engines.data.models import DatasetDiffResult, RecordDiff
from app.engines.data.reason_codes import RecordChangeType


def extract_business_key(record: Dict[str, Any], key_fields: Tuple[str, ...], fallback_idx: int) -> str:
    """Extracts composite business key string from a record dictionary."""
    parts = [str(record.get(k, "")) for k in key_fields if record.get(k) is not None]
    return ":".join(parts) if parts else f"ROW-{fallback_idx}"


def compare_datasets(
    dataset_id: str,
    base_records: List[Dict[str, Any]],
    target_records: List[Dict[str, Any]],
    business_key_fields: Tuple[str, ...],
    base_version: int = 1,
    target_version: int = 2,
) -> DatasetDiffResult:
    """
    Compares two dataset versions and isolates ADDED, REMOVED, MODIFIED, and UNCHANGED records.
    """
    # Index base records by business key
    base_map: Dict[str, Dict[str, Any]] = {}
    base_hashes: Dict[str, str] = {}
    for idx, r in enumerate(base_records):
        bkey = extract_business_key(r, business_key_fields, idx)
        base_map[bkey] = r
        base_hashes[bkey] = compute_record_hash(r)

    # Index target records by business key
    target_map: Dict[str, Dict[str, Any]] = {}
    target_hashes: Dict[str, str] = {}
    for idx, r in enumerate(target_records):
        bkey = extract_business_key(r, business_key_fields, idx)
        target_map[bkey] = r
        target_hashes[bkey] = compute_record_hash(r)

    all_keys: Set[str] = set(base_map.keys()).union(set(target_map.keys()))

    changes: List[RecordDiff] = []
    added_count = 0
    removed_count = 0
    modified_count = 0
    unchanged_count = 0

    for bkey in sorted(all_keys):
        in_base = bkey in base_map
        in_target = bkey in target_map

        if in_target and not in_base:
            # Added
            added_count += 1
            changes.append(
                RecordDiff(
                    record_identifier=bkey,
                    change_type=RecordChangeType.ADDED,
                    field_diffs={k: {"old": None, "new": v} for k, v in target_map[bkey].items() if not k.startswith("_")},
                )
            )
        elif in_base and not in_target:
            # Removed
            removed_count += 1
            changes.append(
                RecordDiff(
                    record_identifier=bkey,
                    change_type=RecordChangeType.REMOVED,
                    field_diffs={k: {"old": v, "new": None} for k, v in base_map[bkey].items() if not k.startswith("_")},
                )
            )
        else:
            # In both -> check if hashes match
            base_h = base_hashes[bkey]
            target_h = target_hashes[bkey]
            if base_h == target_h:
                unchanged_count += 1
                changes.append(
                    RecordDiff(
                        record_identifier=bkey,
                        change_type=RecordChangeType.UNCHANGED,
                        field_diffs={},
                    )
                )
            else:
                # Modified
                modified_count += 1
                r_base = base_map[bkey]
                r_target = target_map[bkey]
                diffs: Dict[str, Dict[str, Any]] = {}
                field_names = set(r_base.keys()).union(set(r_target.keys()))
                for fn in field_names:
                    if fn.startswith("_"):
                        continue
                    v_old = r_base.get(fn)
                    v_new = r_target.get(fn)
                    if v_old != v_new:
                        diffs[fn] = {"old": v_old, "new": v_new}

                changes.append(
                    RecordDiff(
                        record_identifier=bkey,
                        change_type=RecordChangeType.MODIFIED,
                        field_diffs=diffs,
                    )
                )

    summary = (
        f"Dataset {dataset_id} V{base_version} vs V{target_version}: "
        f"{added_count} added, {removed_count} removed, {modified_count} modified, {unchanged_count} unchanged."
    )

    return DatasetDiffResult(
        dataset_id=dataset_id,
        base_version=base_version,
        target_version=target_version,
        total_base_records=len(base_records),
        total_target_records=len(target_records),
        added_count=added_count,
        removed_count=removed_count,
        modified_count=modified_count,
        unchanged_count=unchanged_count,
        changes=changes,
        summary=summary,
    )
