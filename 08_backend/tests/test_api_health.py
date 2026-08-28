import pytest
import importlib
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

backend_app = importlib.import_module("08_backend.app")
app = backend_app.app


def test_health_liveness_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"
    assert data["git_sha"] == "f5f294f2fb6410f1bef0460228256923cc22b9e5"
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0.0


def test_readiness_endpoint_success():
    client = TestClient(app)
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["components"]["database"] is True
    assert data["components"]["postgis"] is True
    assert data["components"]["camera_registry"] is True


def test_readiness_endpoint_database_degraded():
    client = TestClient(app)
    db = importlib.import_module("00_foundation.registry.database")
    with patch.object(db, "get_connection", side_effect=ConnectionError("DB Down")):
        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["database"] is False


def test_metrics_endpoint():
    client = TestClient(app)
    # Perform a request to increment counters
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert "total_requests" in data["metrics"]
    assert data["metrics"]["total_requests"] >= 1
