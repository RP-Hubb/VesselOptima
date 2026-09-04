"""
VesselOptima — CLI Manifest Generator

Generates manifest.json for data/offline/packages/demo-v1/
"""

import json
import sys
from pathlib import Path

# Add backend to PYTHONPATH
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.offline_package.manifest import generate_manifest

PACKAGE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "offline" / "packages" / "demo-v1"

if __name__ == "__main__":
    print(f"Generating manifest for package at: {PACKAGE_DIR}")
    manifest = generate_manifest(PACKAGE_DIR)
    print(f"Successfully generated manifest.json with {manifest['total_files']} files and {manifest['total_rows']:,} rows.")
