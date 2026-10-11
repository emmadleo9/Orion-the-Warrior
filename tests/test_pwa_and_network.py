from fastapi.testclient import TestClient
from orion_app.main import app


def test_cors_headers():
    client = TestClient(app)
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://192.168.18.144:8000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") in ("*", "http://192.168.18.144:8000")


def test_diagnostics_endpoint():
    client = TestClient(app)
    response = client.get("/api/diagnostics")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "cpu" in data
    assert "memory" in data
    assert "disk" in data
    assert "uptime" in data


def test_system_metrics_endpoint():
    client = TestClient(app)
    response = client.get("/api/system/metrics")
    assert response.status_code == 200
    data = response.json()
    # Check both flat and nested keys
    assert "cpu_percent" in data
    assert "memory_percent" in data
    assert "disk_percent" in data
    assert isinstance(data["cpu_percent"], (int, float))
    assert isinstance(data["memory_percent"], (int, float))
    assert "cpu" in data
    assert "usage_percent" in data["cpu"]


def test_pwa_manifest_and_sw():
    client = TestClient(app)
    sw_res = client.get("/sw.js")
    assert sw_res.status_code == 200
    assert "serviceWorker" in sw_res.text or "CACHE_NAME" in sw_res.text

    manifest_res = client.get("/manifest.json")
    assert manifest_res.status_code == 200
    manifest = manifest_res.json()
    assert manifest["name"] == "Orion The Warrior"
    assert manifest["display"] == "standalone"

