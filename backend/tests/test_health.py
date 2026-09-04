"""
VesselOptima — Health Endpoint Tests
"""


def test_root_endpoint(client):
    """Application root returns status and mode."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "VesselOptima"
    assert data["status"] == "running"
    assert data["mode"] in ("LIVE", "OFFLINE_DEMO")


def test_health_endpoint(client):
    """Health check returns database and runtime status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded", "unhealthy")
    assert data["database"] in ("healthy", "unhealthy")
    assert data["runtime_mode"] in ("LIVE", "OFFLINE_DEMO")
    assert "timestamp" in data


def test_health_v1_endpoint(client):
    """Versioned health check works identically."""
    response = client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded", "unhealthy")


def test_mode_header_present(client):
    """Every response includes X-VesselOptima-Mode header."""
    response = client.get("/")
    assert "X-VesselOptima-Mode" in response.headers
    assert response.headers["X-VesselOptima-Mode"] in ("LIVE", "OFFLINE_DEMO")
    assert "X-Data-Context-ID" in response.headers
