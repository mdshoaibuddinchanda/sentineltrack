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
    assert "git_sha" in data
    assert len(data["git_sha"]) >= 7
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
    assert data["components"]["vehicle_detector"] is True
    assert data["components"]["tracker"] is True
    assert data["components"]["plate_detector"] is True
    assert data["components"]["ocr_pipeline"] is True
    assert data["components"]["target_pipeline"] is True


def test_readiness_endpoint_database_degraded():
    client = TestClient(app)
    db = importlib.import_module("00_foundation.registry.database")
    with patch.object(db, "get_connection", side_effect=ConnectionError("DB Down")):
        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["database"] is False


def test_readiness_endpoint_cv_model_degraded():
    client = TestClient(app)
    analytics_mod = importlib.import_module("08_backend.services.analytics_service")
    worker = analytics_mod.get_analytics_worker()

    fake_status = {
        "running": True,
        "active_camera_count": 0,
        "queues": {},
        "models_loaded": {
            "detector": True,
            "tracker": True,
            "plate_detector": False,  # Simulated plate model load failure
            "plate_pipeline": False,
            "ocr_pipeline": True,
            "target_pipeline": True
        }
    }

    with patch.object(worker, "get_status", return_value=fake_status):
        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["plate_detector"] is False


def test_readiness_reports_no_live_frames_after_catalogue_success():
    analytics_mod = importlib.import_module("08_backend.services.analytics_service")
    scale_mod = importlib.import_module("11_scale_deployment.config")
    lifecycle_mod = importlib.import_module("08_backend.lifecycle")
    worker = analytics_mod.get_analytics_worker()
    fake_models = {
        "detector": True,
        "tracker": True,
        "plate_detector": True,
        "ocr_pipeline": True,
        "target_pipeline": True,
    }
    fake_supervisor = MagicMock()
    fake_supervisor.get_status.return_value = {
        "running": True,
        "total_cameras": 30,
        "connected_cameras": 0,
        "total_frames_decoded": 0,
        "cameras": {},
    }
    fake_config = MagicMock(enable_stream_ingestion=True)

    with (
        patch.object(worker, "_lazy_init_models", return_value=None),
        patch.object(worker, "get_status", return_value={"models_loaded": fake_models}),
        patch.object(scale_mod, "get_scale_config", return_value=fake_config),
        patch.object(lifecycle_mod, "get_stream_supervisor", return_value=fake_supervisor),
        patch.object(
            lifecycle_mod,
            "get_stream_ingestion_diagnostics",
            return_value={"code": "READY", "message": "Catalogue refreshed."},
        ),
    ):
        response = TestClient(app).get("/ready")

    assert response.status_code == 503
    stream = response.json()["details"]["stream_ingestion"]
    assert stream["reason"] == "NO_LIVE_FRAMES"
    assert "none has delivered" in stream["message"]


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
