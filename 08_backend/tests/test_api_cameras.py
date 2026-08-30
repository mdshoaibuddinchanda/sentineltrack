import pytest
import importlib
import asyncio
from fastapi.testclient import TestClient

backend_app = importlib.import_module("08_backend.app")
cam_repo_mod = importlib.import_module("07_route_engine.camera_repository")
models_mod = importlib.import_module("07_route_engine.models")
camera_service_mod = importlib.import_module("08_backend.services.camera_service")
camera_router_mod = importlib.import_module("08_backend.routers.cameras")
lifecycle_mod = importlib.import_module("08_backend.lifecycle")

app = backend_app.app
CameraGeo = models_mod.CameraGeo
LocationQuality = models_mod.LocationQuality
PostgresCameraRepository = cam_repo_mod.PostgresCameraRepository


def test_list_cameras_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/cameras?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    if data["items"]:
        cam = data["items"][0]
        assert "camera_id" in cam
        # Verify private credentials are not exposed
        assert "password" not in cam
        assert "rtsp_url" not in cam


def test_get_camera_detail_success():
    cam_repo = PostgresCameraRepository()
    cam = CameraGeo("test_cam_detail_01", "Test Junction Detail", 23.0200, 72.5700, location_quality=LocationQuality.VERIFIED)
    cam_repo.save_camera(cam)

    client = TestClient(app)
    response = client.get("/api/v1/cameras/test_cam_detail_01")
    assert response.status_code == 200
    data = response.json()
    assert data["camera_id"] == "test_cam_detail_01"
    assert data["name"] == "Test Junction Detail"
    assert data["latitude"] == 23.0200
    assert data["longitude"] == 72.5700


def test_get_camera_detail_not_found():
    client = TestClient(app)
    response = client.get("/api/v1/cameras/NONEXISTENT_CAM_999")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "CAMERA_NOT_FOUND"


def test_get_camera_health_endpoint():
    cam_repo = PostgresCameraRepository()
    cam = CameraGeo("test_cam_health_01", "Test Junction Health", 23.0300, 72.5800)
    cam_repo.save_camera(cam)

    client = TestClient(app)
    response = client.get("/api/v1/cameras/test_cam_health_01/health")
    assert response.status_code == 200
    data = response.json()
    assert data["camera_id"] == "test_cam_health_01"
    assert "stream_status" in data
    assert data["connected"] is False
    assert data["frames_decoded"] == 0
    assert data["first_frame_latency_ms"] is None


def test_live_camera_endpoint_returns_authenticated_mjpeg_response(monkeypatch):
    class FakeService:
        def get_camera_by_id(self, camera_id):
            return type("Camera", (), {"camera_id": camera_id})()

    class FakeMetrics:
        def inc_requests(self):
            return None

    class FakeSupervisor:
        def get_live_snapshot(self, camera_id):
            return (object(), 1.0)

    monkeypatch.setattr(lifecycle_mod, "get_stream_supervisor", lambda: FakeSupervisor())
    response = asyncio.run(
        camera_router_mod.get_camera_live_stream(
            "test_cam_live_01",
            service=FakeService(),
            metrics=FakeMetrics(),
        )
    )

    assert response.media_type.startswith("multipart/x-mixed-replace")
    assert response.headers["cache-control"].startswith("no-store")


def test_inactive_registry_row_cannot_look_like_a_live_connection():
    status = camera_service_mod._runtime_stream_status(
        "inactive-test-camera",
        "ONLINE",
        live=False,
        source_configured=False,
        runtime_state=None,
    )
    assert status == "NOT_CONFIGURED"


def test_persisted_online_probe_cannot_look_live_without_a_worker():
    status = camera_service_mod._runtime_stream_status(
        "configured-but-inactive-worker",
        "ONLINE",
        live=True,
        source_configured=True,
        runtime_state=None,
    )
    assert status == "UNKNOWN"


def test_search_nearby_cameras_by_coordinates():
    cam_repo = PostgresCameraRepository()
    cam = CameraGeo("test_cam_nearby_01", "Near Point", 23.0200, 72.5700)
    cam_repo.save_camera(cam)

    client = TestClient(app)
    response = client.get("/api/v1/cameras/nearby?lat=23.0200&lon=72.5700&radius_m=1000")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(c["camera_id"] == "test_cam_nearby_01" for c in data)


def test_search_nearby_cameras_invalid_coordinates():
    client = TestClient(app)
    # Latitude out of bounds
    response = client.get("/api/v1/cameras/nearby?lat=195.0&lon=72.5700&radius_m=1000")
    assert response.status_code == 422
