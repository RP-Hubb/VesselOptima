"""
VesselOptima — CLI Offline Package Verifier

Verifies package manifest integrity, SHA-256 hashes, row counts, and domain validation.
"""

import sys
from pathlib import Path

# Add backend to PYTHONPATH
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.offline_package.manifest import verify_manifest
from app.services.offline_package.validator import validate_package_data

PACKAGE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "offline" / "packages" / "demo-v1"

if __name__ == "__main__":
    print(f"Auditing offline package integrity at: {PACKAGE_DIR}")
    try:
        manifest_res = verify_manifest(PACKAGE_DIR)
        print(f"[PASS] Manifest integrity verified: {manifest_res['files_verified']} files, {manifest_res['total_rows']:,} rows.")
        print(f"       Manifest hash: {manifest_res['manifest_hash']}")

        domain_res = validate_package_data(PACKAGE_DIR)
        print(f"[PASS] Domain & referential integrity verified across all {manifest_res['files_verified']} datasets.")
        print("ALL VERIFICATION CHECKS PASSED.")
    except Exception as e:
        print(f"[FAIL] Offline package integrity error: {e}")
        sys.exit(1)
