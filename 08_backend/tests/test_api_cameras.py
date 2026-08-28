import pytest
import importlib
from fastapi.testclient import TestClient

backend_app = importlib.import_module("08_backend.app")
cam_repo_mod = importlib.import_module("07_route_engine.camera_repository")
models_mod = importlib.import_module("07_route_engine.models")

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
