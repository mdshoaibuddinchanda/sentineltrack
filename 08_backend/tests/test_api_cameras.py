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


@pytest.fixture(autouse=True)
def cleanup_camera_test_rows():
    yield
    db = importlib.import_module("00_foundation.registry.database")
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM camera_health_events WHERE camera_id LIKE 'test_cam_%';")
            cur.execute("DELETE FROM cameras WHERE camera_id LIKE 'test_cam_%';")


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


def test_manual_camera_onboarding_and_duplicate_protection():
    client = TestClient(app)
    payload = {
        "camera_id": "test_cam_onboard_01",
        "name": "Surveyed Junction",
        "department": "Traffic",
        "organization": "Test Police",
        "source_system": "TEST_VMS",
        "external_id": "junction-01",
        "latitude": 23.0225,
        "longitude": 72.5714,
        "location_quality": "VERIFIED",
        "coordinate_source": "Test survey sheet 2026-09-02",
        "coordinate_accuracy_m": 3.0,
        "coverage_radius_m": 125.0,
        "live": False,
    }
    response = client.post("/api/v1/cameras", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["camera"]["location_quality"] == "VERIFIED"
    assert body["camera"]["coordinate_source"] == "Test survey sheet 2026-09-02"
    assert "rtsp_url" not in body["camera"]

    duplicate = client.post("/api/v1/cameras", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_CAMERA"


def test_coordinates_require_explicit_provenance():
    client = TestClient(app)
    response = client.post(
        "/api/v1/cameras",
        json={
            "camera_id": "test_cam_missing_provenance",
            "latitude": 23.0,
            "longitude": 72.0,
            "location_quality": "VERIFIED",
        },
    )
    assert response.status_code == 422


def test_selected_camera_can_be_enriched_with_audited_gps_metadata():
    client = TestClient(app)
    created = client.post(
        "/api/v1/cameras",
        json={
            "camera_id": "test_cam_update_01",
            "name": "Location awaiting survey",
            "source_system": "MANUAL",
            "live": False,
        },
    )
    assert created.status_code == 201

    updated = client.patch(
        "/api/v1/cameras/test_cam_update_01/registry",
        json={
            "department": "Traffic Police",
            "organization": "Test Organization",
            "latitude": 23.025,
            "longitude": 72.575,
            "location_quality": "VERIFIED",
            "coordinate_source": "Official GIS record TEST-42",
            "azimuth": 180.0,
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["created"] is False
    assert body["worker_status"] == "UNCHANGED"
    assert body["camera"]["department"] == "Traffic Police"
    assert body["camera"]["latitude"] == 23.025
    assert body["camera"]["coordinate_source"] == "Official GIS record TEST-42"


def test_camera_update_rejects_a_partial_coordinate_pair_without_internal_error():
    client = TestClient(app)
    assert client.post(
        "/api/v1/cameras",
        json={"camera_id": "test_cam_update_invalid", "source_system": "MANUAL", "live": False},
    ).status_code == 201
    response = client.patch(
        "/api/v1/cameras/test_cam_update_invalid/registry",
        json={"latitude": 23.025},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_CAMERA_REGISTRY"


def test_camera_bulk_dry_run_does_not_persist_then_apply_does():
    client = TestClient(app)
    payload = {
        "dry_run": True,
        "mode": "CREATE_ONLY",
        "cameras": [
            {
                "camera_id": "test_cam_bulk_01",
                "name": "Bulk Camera",
                "organization": "Test Organization",
                "source_system": "TEST_BULK",
                "live": False,
            }
        ],
    }
    preview = client.post("/api/v1/cameras/bulk", json=payload)
    assert preview.status_code == 200
    assert preview.json()["items"][0]["status"] == "WOULD_CREATE"
    assert client.get("/api/v1/cameras/test_cam_bulk_01").status_code == 404

    payload["dry_run"] = False
    applied = client.post("/api/v1/cameras/bulk", json=payload)
    assert applied.status_code == 200
    assert applied.json()["created"] == 1
    assert applied.json()["items"][0]["status"] == "CREATED"
    assert client.get("/api/v1/cameras/test_cam_bulk_01").status_code == 200


def test_camera_bulk_rejects_every_occurrence_of_a_duplicate_batch_id():
    client = TestClient(app)
    record = {
        "camera_id": "test_cam_bulk_duplicate",
        "source_system": "TEST_BULK",
        "live": False,
    }
    response = client.post(
        "/api/v1/cameras/bulk",
        json={"dry_run": False, "mode": "CREATE_ONLY", "cameras": [record, record]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] == 0
    assert body["created"] == 0
    assert body["skipped"] == 2
    assert {item["status"] for item in body["items"]} == {"SKIPPED"}
    assert client.get("/api/v1/cameras/test_cam_bulk_duplicate").status_code == 404


def test_gap_analysis_geojson_and_coverage_are_truthful():
    client = TestClient(app)
    create = client.post(
        "/api/v1/cameras",
        json={
            "camera_id": "test_cam_coverage_01",
            "name": "Coverage Camera",
            "organization": "Test Organization",
            "source_system": "TEST_GIS",
            "latitude": 23.0225,
            "longitude": 72.5714,
            "location_quality": "VERIFIED",
            "coordinate_source": "Survey control point",
            "coverage_radius_m": 100.0,
            "live": False,
        },
    )
    assert create.status_code == 201

    gap = client.get("/api/v1/cameras/gap-analysis")
    assert gap.status_code == 200
    assert gap.json()["total_cameras"] >= 1
    assert "Missing coordinates are reported, never inferred from camera names." in gap.json()["limitations"]

    geojson = client.get("/api/v1/cameras/export.geojson")
    assert geojson.status_code == 200
    feature = next(item for item in geojson.json()["features"] if item["id"] == "test_cam_coverage_01")
    assert feature["geometry"]["coordinates"] == [72.5714, 23.0225]
    assert "rtsp_url" not in feature["properties"]

    coverage = client.post(
        "/api/v1/cameras/coverage-analysis",
        json={
            "area_of_interest": {
                "type": "Polygon",
                "coordinates": [[
                    [72.5700, 23.0210],
                    [72.5730, 23.0210],
                    [72.5730, 23.0240],
                    [72.5700, 23.0240],
                    [72.5700, 23.0210],
                ]],
            },
            "default_coverage_radius_m": 100,
            "include_approximate": False,
        },
    )
    assert coverage.status_code == 200
    result = coverage.json()
    assert result["eligible_camera_count"] >= 1
    assert 0.0 < result["coverage_percent"] <= 100.0
    assert result["coverage_model"] == "PLANNING_BUFFER_APPROXIMATION"


def test_connector_inventory_is_secret_free_and_disabled_by_default():
    client = TestClient(app)
    response = client.get("/api/v1/cameras/connectors")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert all(item["enabled"] is False for item in body["items"])
    serialized = response.text.lower()
    assert "password_env" not in serialized
    assert "bearer_token_env" not in serialized
