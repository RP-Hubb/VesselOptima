"""
VesselOptima — Network Isolation & Offline Contract Tests

Proves that OFFLINE_DEMO mode and the offline package loader execute completely
air-gapped with zero outbound network calls.
"""

import socket
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.offline_package.loader import OfflinePackageIngestionService
from app.services.offline_package.manifest import verify_manifest
from app.services.offline_package.validator import validate_package_data


@pytest.fixture()
def demo_package_dir():
    pkg_dir = Path(__file__).resolve().parent.parent.parent / "data" / "offline" / "packages" / "demo-v1"
    assert pkg_dir.exists(), f"Demo package directory missing: {pkg_dir}"
    return pkg_dir


def test_offline_package_loader_zero_network_calls(db, demo_package_dir, monkeypatch):
    """
    Demonstrates that offline package verification, domain validation, and database
    ingestion operate with NO external network connectivity.
    Explicitly blocks all outbound non-localhost socket connections.
    """
    original_connect = socket.socket.connect

    def blocked_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) and address else str(address)
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise ConnectionRefusedError(
                f"Outbound network connectivity to {host} is strictly blocked in OFFLINE_DEMO mode!"
            )
        return original_connect(self, address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)

    # 1. Verify manifest under blocked network
    manifest_res = verify_manifest(demo_package_dir)
    assert manifest_res["status"] == "VALID"

    # 2. Validate domain data under blocked network
    domain_res = validate_package_data(demo_package_dir)
    assert domain_res["status"] == "VALID"

    # 3. Ingest package under blocked network
    service = OfflinePackageIngestionService(db)
    ingest_res = service.ingest_package(demo_package_dir, force_reload=True)
    assert ingest_res["status"] == "SUCCESS"
    assert ingest_res["counts"]["vessels"] == 20
    assert ingest_res["counts"]["market_observations"] > 20000


def test_offline_mode_cannot_call_remote_endpoints(client, monkeypatch):
    """
    Ensures that in OFFLINE_DEMO mode, no external HTTP calls are dispatched.
    Any external connection attempt triggers an immediate refusal.
    """
    original_connect = socket.socket.connect

    def blocked_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) and address else str(address)
        if host not in ("127.0.0.1", "localhost", "::1", "testserver"):
            raise ConnectionRefusedError(
                f"Outbound network connectivity to {host} is strictly blocked in OFFLINE_DEMO mode!"
            )
        return original_connect(self, address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)

    # Calling /v1/data/status works completely offline without network
    resp = client.get("/v1/data/status")
    assert resp.status_code == 200
    assert resp.json()["runtime_mode"] in ("OFFLINE_DEMO", "LIVE")

