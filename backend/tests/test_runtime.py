"""
VesselOptima — Runtime Mode Endpoint Tests

Tests the two-mode contract: only LIVE and OFFLINE_DEMO are accepted.
No hybrid, no third mode, no automatic fallback.
"""


def test_get_mode_default(client):
    """Default mode is returned when no mode switch has occurred."""
    response = client.get("/v1/runtime/mode")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] in ("LIVE", "OFFLINE_DEMO")
    assert "mode_session_id" in data
    assert "selected_at" in data


def test_switch_to_live(client):
    """Switching to LIVE mode succeeds with confirmation."""
    response = client.put("/v1/runtime/mode", json={
        "mode": "LIVE",
        "confirmation": True,
        "reason": "Test: switching to LIVE"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "LIVE"
    assert data["data_context_id"] == "live-context"


def test_switch_to_offline_demo(client):
    """Switching to OFFLINE_DEMO mode succeeds with confirmation."""
    response = client.put("/v1/runtime/mode", json={
        "mode": "OFFLINE_DEMO",
        "confirmation": True,
        "reason": "Test: switching to OFFLINE_DEMO"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "OFFLINE_DEMO"
    assert data["data_context_id"] == "offline-demo-context"


def test_switch_requires_confirmation(client):
    """Mode switch without confirmation is rejected."""
    response = client.put("/v1/runtime/mode", json={
        "mode": "LIVE",
        "confirmation": False,
    })
    assert response.status_code == 400


def test_reject_invalid_mode(client):
    """Invalid mode values (HYBRID, AUTO, etc.) are rejected."""
    response = client.put("/v1/runtime/mode", json={
        "mode": "HYBRID",
        "confirmation": True,
    })
    assert response.status_code == 422


def test_reject_auto_mode(client):
    """AUTO mode does not exist — rejected."""
    response = client.put("/v1/runtime/mode", json={
        "mode": "AUTO",
        "confirmation": True,
    })
    assert response.status_code == 422


def test_reject_cached_mode(client):
    """CACHED mode does not exist — rejected."""
    response = client.put("/v1/runtime/mode", json={
        "mode": "CACHED",
        "confirmation": True,
    })
    assert response.status_code == 422


def test_runtime_status(client):
    """Runtime status endpoint returns structured information."""
    response = client.get("/v1/runtime/status")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] in ("LIVE", "OFFLINE_DEMO")
    assert data["app_status"] in ("ready", "degraded", "error")
    assert data["database_status"] in ("healthy", "unhealthy")
    assert "timestamp" in data


def test_no_third_mode_exists(client):
    """Verify that there is no third runtime mode.
    This test explicitly checks the enum boundary."""
    invalid_modes = [
        "HYBRID", "AUTO", "CACHED", "FALLBACK", "MIXED",
        "LIVE_CACHED", "OFFLINE", "DEMO", "PARTIAL",
    ]
    for mode in invalid_modes:
        response = client.put("/v1/runtime/mode", json={
            "mode": mode,
            "confirmation": True,
        })
        assert response.status_code == 422, f"Mode '{mode}' should be rejected but got {response.status_code}"


def test_offline_package_enumeration(client):
    """DEF-011: Runtime status enumerates available offline packages on disk."""
    response = client.get("/v1/runtime/status")
    assert response.status_code == 200
    data = response.json()
    assert "available_packages" in data
    assert isinstance(data["available_packages"], list)
    assert len(data["available_packages"]) > 0
    assert "demo-v1" in data["available_packages"]


def test_live_mode_transparency(client):
    """DEF-004: Switching to LIVE mode explicitly surfaces non-operational source status."""
    # Switch to LIVE mode
    client.put("/v1/runtime/mode", json={"mode": "LIVE", "confirmation": True, "reason": "Testing live transparency"})
    try:
        response = client.get("/v1/runtime/status")
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "LIVE"
        assert data["is_live_operational"] is False
        assert data["app_status"] == "degraded"
        assert len(data["sources"]) > 0
        for s in data["sources"]:
            assert s["status"] == "unavailable"
            assert "Live API credentials not configured" in s["error"]
    finally:
        # Switch back to OFFLINE_DEMO
        client.put("/v1/runtime/mode", json={"mode": "OFFLINE_DEMO", "confirmation": True, "reason": "Restoring demo mode"})
