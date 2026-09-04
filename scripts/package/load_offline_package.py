"""
VesselOptima — CLI Package Ingestion Runner

Loads data/offline/packages/demo-v1 into the active database.
"""

import sys
from pathlib import Path

# Add backend to PYTHONPATH
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.services.offline_package.loader import OfflinePackageIngestionService

PACKAGE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "offline" / "packages" / "demo-v1"

if __name__ == "__main__":
    force = "--force" in sys.argv
    print(f"Loading offline package from: {PACKAGE_DIR} (force_reload={force})")

    db = SessionLocal()
    try:
        service = OfflinePackageIngestionService(db)
        res = service.ingest_package(PACKAGE_DIR, force_reload=force)
        print(f"Ingestion result: {res['status']}")
        if res.get("counts"):
            print("Records ingested:")
            for k, v in res["counts"].items():
                print(f"  - {k}: {v:,}")
        if res.get("message"):
            print(f"Message: {res['message']}")
    except Exception as e:
        print(f"Ingestion error: {e}")
        sys.exit(1)
    finally:
        db.close()
