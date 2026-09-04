"""
VesselOptima — Offline Data Quality Report Utility

Produces a comprehensive data quality audit across all datasets in an offline package:
- Row and column counts
- Missing value analysis
- Duplicate row detection
- Date coverage
- Provenance classification
- Schema version
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


def generate_data_quality_report(package_dir: Path) -> Dict[str, Any]:
    """Scans all CSV datasets in package_dir and computes data quality metrics."""
    if not package_dir.exists():
        raise FileNotFoundError(f"Package directory not found: {package_dir}")

    csv_files: List[Path] = sorted(package_dir.rglob("*.csv"))
    report_items = []
    total_rows = 0
    total_missing = 0
    total_duplicates = 0

    for csv_file in csv_files:
        rel_path = csv_file.relative_to(package_dir).as_posix()
        dataset_name = csv_file.stem

        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            rows = list(reader)

        row_count = len(rows)
        total_rows += row_count
        col_count = len(fieldnames)

        # Count missing values
        missing_count = 0
        seen_rows = set()
        duplicate_count = 0
        date_min = None
        date_max = None

        date_col = next((c for c in fieldnames if "date" in c or "observed_at" in c or "start" in c), None)

        for r in rows:
            # Check empty values
            for k, v in r.items():
                if v is None or v.strip() == "":
                    missing_count += 1

            # Check duplicates (tuple of all values)
            row_tuple = tuple(r[k] for k in fieldnames)
            if row_tuple in seen_rows:
                duplicate_count += 1
            else:
                seen_rows.add(row_tuple)

            # Check date coverage
            if date_col and r.get(date_col):
                d_val = r[date_col][:10]
                if not date_min or d_val < date_min:
                    date_min = d_val
                if not date_max or d_val > date_max:
                    date_max = d_val

        total_missing += missing_count
        total_duplicates += duplicate_count

        provenance = "SYNTHETIC"
        if "freight" in rel_path:
            provenance = "PROXY"
        elif "employment" in rel_path:
            provenance = "DERIVED"

        coverage_str = f"{date_min} to {date_max}" if date_min and date_max else "N/A (Dimensional)"

        report_items.append({
            "dataset": rel_path,
            "name": dataset_name,
            "rows": row_count,
            "columns": col_count,
            "missing_values": missing_count,
            "duplicate_rows": duplicate_count,
            "date_coverage": coverage_str,
            "provenance": provenance,
            "schema_version": "1.0.0",
        })

    return {
        "package_dir": str(package_dir),
        "total_datasets": len(report_items),
        "total_rows": total_rows,
        "total_missing_values": total_missing,
        "total_duplicate_rows": total_duplicates,
        "datasets": report_items,
    }


def format_quality_report_markdown(report: Dict[str, Any]) -> str:
    """Formats the data quality report as a markdown table."""
    lines = [
        "# VesselOptima — Data Quality Audit Report",
        f"**Target Package:** `{report['package_dir']}`  ",
        f"**Total Datasets:** {report['total_datasets']} | **Total Rows:** {report['total_rows']:,} | **Missing Values:** {report['total_missing_values']} | **Duplicates:** {report['total_duplicate_rows']}",
        "",
        "| Dataset | Rows | Cols | Missing | Dups | Coverage | Provenance | Schema |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d in report["datasets"]:
        lines.append(
            f"| `{d['dataset']}` | {d['rows']:,} | {d['columns']} | {d['missing_values']} | {d['duplicate_rows']} | {d['date_coverage']} | `{d['provenance']}` | {d['schema_version']} |"
        )
    lines.append("")
    return "\n".join(lines)
