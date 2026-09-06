"""
VesselOptima — Phase 12 Maritime Data Integration & Quality Governance
Local File Adapter for Air-Gapped CSV and JSON Ingestion
"""

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from app.engines.data.adapters.base import DataSourceAdapter
from app.engines.data.reason_codes import DataGovernanceReasonCode


class LocalFileAdapter(DataSourceAdapter):
    """
    Air-gapped adapter for importing local CSV and JSON datasets.
    Zero external network calls.
    """

    def extract_raw_records(
        self,
        source_payload: Union[str, Path, bytes],
        filename: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Reads local CSV or JSON text/bytes and extracts uniform list of raw dictionaries.
        """
        raw_bytes: bytes
        origin_filename: str = filename or "in_memory_import"

        if isinstance(source_payload, list):
            records = source_payload
            raw_bytes = json.dumps(source_payload, sort_keys=True).encode("utf-8")
            original_hash = hashlib.sha256(raw_bytes).hexdigest()
            metadata = {
                "source_name": origin_filename,
                "source_type": "LOCAL_FILE",
                "original_filename": origin_filename,
                "original_hash": original_hash,
                "raw_size_bytes": len(raw_bytes),
                "format": "JSON",
                "extracted_count": len(records),
            }
            return records, metadata

        if isinstance(source_payload, dict):
            records = source_payload.get("records") or source_payload.get("data") or [source_payload]
            raw_bytes = json.dumps(source_payload, sort_keys=True).encode("utf-8")
            original_hash = hashlib.sha256(raw_bytes).hexdigest()
            metadata = {
                "source_name": origin_filename,
                "source_type": "LOCAL_FILE",
                "original_filename": origin_filename,
                "original_hash": original_hash,
                "raw_size_bytes": len(raw_bytes),
                "format": "JSON",
                "extracted_count": len(records),
            }
            return records, metadata

        if isinstance(source_payload, Path) or (
            isinstance(source_payload, str) and (Path(source_payload).exists() or "/" in source_payload or "\\" in source_payload)
        ):
            path = Path(source_payload)
            if not path.exists():
                # Might be raw text string passed as string
                raw_bytes = str(source_payload).encode("utf-8")
            else:
                origin_filename = path.name
                raw_bytes = path.read_bytes()
        elif isinstance(source_payload, bytes):
            raw_bytes = source_payload
        else:
            raw_bytes = str(source_payload).encode("utf-8")

        # Compute SHA-256 of raw content
        original_hash = hashlib.sha256(raw_bytes).hexdigest()

        # Detect format
        text_content = raw_bytes.decode("utf-8-sig", errors="replace")
        records = []

        is_json = False
        trimmed = text_content.strip()
        if (trimmed.startswith("{") and trimmed.endswith("}")) or (
            trimmed.startswith("[") and trimmed.endswith("]")
        ):
            try:
                parsed_json = json.loads(trimmed)
                is_json = True
                if isinstance(parsed_json, list):
                    records = parsed_json
                elif isinstance(parsed_json, dict):
                    records = parsed_json.get("records") or parsed_json.get("data") or [parsed_json]
            except Exception:
                is_json = False

        if not is_json:
            # Parse as CSV
            f = io.StringIO(text_content)
            reader = csv.reader(f)
            header_row = next(reader, None)
            if not header_row:
                return [], {
                    "source_name": origin_filename,
                    "source_type": "LOCAL_FILE",
                    "original_filename": origin_filename,
                    "original_hash": original_hash,
                    "raw_size_bytes": len(raw_bytes),
                    "duplicate_columns": [],
                }

            # Check for duplicate headers
            clean_headers = [h.strip() for h in header_row]
            header_counts: Dict[str, int] = {}
            duplicates: List[str] = []
            for h in clean_headers:
                header_counts[h] = header_counts.get(h, 0) + 1
                if header_counts[h] == 2:
                    duplicates.append(h)

            for row in reader:
                if not row or not any(field.strip() for field in row):
                    continue
                record_dict: Dict[str, Any] = {}
                for idx, col_name in enumerate(clean_headers):
                    val = row[idx].strip() if idx < len(row) else ""
                    record_dict[col_name] = val
                records.append(record_dict)

        metadata = {
            "source_name": origin_filename,
            "source_type": "LOCAL_FILE",
            "original_filename": origin_filename,
            "original_hash": original_hash,
            "raw_size_bytes": len(raw_bytes),
            "format": "JSON" if is_json else "CSV",
            "extracted_count": len(records),
        }

        return records, metadata
