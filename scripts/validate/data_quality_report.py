"""
VesselOptima — CLI Data Quality Auditor

Generates and displays the comprehensive data quality audit report.
"""

import sys
from pathlib import Path

# Add backend to PYTHONPATH
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.offline_package.quality_report import (
    format_quality_report_markdown,
    generate_data_quality_report,
)

PACKAGE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "offline" / "packages" / "demo-v1"

if __name__ == "__main__":
    report = generate_data_quality_report(PACKAGE_DIR)
    md = format_quality_report_markdown(report)
    print(md)
