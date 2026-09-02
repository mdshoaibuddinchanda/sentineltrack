import uuid
import pytest
import importlib
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

backend_app = importlib.import_module("08_backend.app")
p5_models = importlib.import_module("05_target_matching.models")
p5_repo = importlib.import_module("05_target_matching.repository")
p7_models = importlib.import_module("07_route_engine.models")
p7_cam_repo = importlib.import_module("07_route_engine.camera_repository")

app = backend_app.app


def test_camera_pair_feasibility_demo_uses_registry_without_persisting_sightings():
    cam_repo_mod = importlib.import_module("07_route_engine.camera_repository")
    models_mod = importlib.import_module("07_route_engine.models")
    cam_repo = cam_repo_mod.PostgresCameraRepository()
    cam_repo.save_camera(models_mod.CameraGeo(
        "test_cam_route_from", "Route From", 23.0200, 72.5700,
        location_quality=models_mod.LocationQuality.VERIFIED,
    ))
    cam_repo.save_camera(models_mod.CameraGeo(
        "test_cam_route_to", "Route To", 23.1200, 72.6700,
        location_quality=models_mod.LocationQuality.VERIFIED,
    ))
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/routes/feasibility-check",
            json={
                "from_camera_id": "test_cam_route_from",
                "to_camera_id": "test_cam_route_to",
                "elapsed_seconds": 30,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["distance_lower_bound_m"] > 0
        assert body["feasibility"] in {"QUESTIONABLE", "IMPOSSIBLE"}
        assert "not a road route" in body["disclaimer"].lower()
    finally:
        db = importlib.import_module("00_foundation.registry.database")
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM cameras WHERE camera_id IN ('test_cam_route_from', 'test_cam_route_to')"
                )
Sighting = p5_models.Sighting
MatchClass = p5_models.MatchClass
PostgresTargetMatchingRepository = p5_repo.PostgresTargetMatchingRepository
PostgresCameraRepository = p7_cam_repo.PostgresCameraRepository
CameraGeo = p7_models.CameraGeo
LocationQuality = p7_models.LocationQuality


def test_get_target_route_endpoint():
    # 1. Register test cameras
    cam_repo = PostgresCameraRepository()
    c1 = CameraGeo("cam_route_api_1", "Junction A", 23.0200, 72.5700, location_quality=LocationQuality.VERIFIED)
    c2 = CameraGeo("cam_route_api_2", "Junction B", 23.0400, 72.5800, location_quality=LocationQuality.VERIFIED)
    cam_repo.save_camera(c1)
    cam_repo.save_camera(c2)

    # 2. Insert sightings for route
    target_plate = f"GJ01ROUTE{uuid.uuid4().hex[:4].upper()}"
    t0 = datetime(2026, 8, 28, 11, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=6)

    target_repo = PostgresTargetMatchingRepository()
    target_repo.save_sighting(Sighting(
        sighting_id=str(uuid.uuid4()),
        camera_id="cam_route_api_1",
        stream_epoch=1,
        track_id=101,
        first_pts_ms=0.0,
        last_pts_ms=1000.0,
        registration_candidate=target_plate,
        confidence=0.98,
        match_score=0.95,
        match_class=MatchClass.EXACT,
        created_at=t0,
        event_time_utc=t0,
        event_time_source="SOURCE_WALLCLOCK",
        event_time_quality="HIGH"
    ))
    target_repo.save_sighting(Sighting(
        sighting_id=str(uuid.uuid4()),
        camera_id="cam_route_api_2",
        stream_epoch=1,
        track_id=202,
        first_pts_ms=5000.0,
        last_pts_ms=6000.0,
        registration_candidate=target_plate,
        confidence=0.95,
        match_score=0.92,
        match_class=MatchClass.HIGH_PROBABILITY,
        created_at=t1,
        event_time_utc=t1,
        event_time_source="SOURCE_WALLCLOCK",
        event_time_quality="HIGH"
    ))

    client = TestClient(app)
    # 3. Query route API
    res = client.get(f"/api/v1/routes/{target_plate}")
    assert res.status_code == 200
    data = res.json()
    assert data["registration"] == target_plate
    assert data["status"] == "CONFIRMED_SEQUENCE"
    assert data["sighting_count"] == 2
    assert data["camera_count"] == 2
    assert data["sightings"][0]["location_label"] == "Junction A"
    assert len(data["segments"]) == 1
    assert data["segments"][0]["feasibility"] == "FEASIBLE"
    assert "LineString connects observed camera sightings" in data["disclaimer"]

    report = client.get(f"/api/v1/routes/{target_plate}/report.csv")
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in report.headers["content-disposition"]
    assert "generated_at_utc" in report.text
    assert "sighting_sequence" in report.text
    assert "SOURCE_WALLCLOCK" in report.text
    assert "Junction A" in report.text


def test_get_target_route_geojson_rfc_validation():
    target_plate = f"GJ01GEO{uuid.uuid4().hex[:4].upper()}"
    cam_repo = PostgresCameraRepository()
    c1 = CameraGeo("cam_geo_api_1", "Junction Alpha", 23.0200, 72.5700)
    cam_repo.save_camera(c1)

    target_repo = PostgresTargetMatchingRepository()
    target_repo.save_sighting(Sighting(
        sighting_id=str(uuid.uuid4()),
        camera_id="cam_geo_api_1",
        stream_epoch=1,
        track_id=1,
        first_pts_ms=0.0,
        last_pts_ms=100.0,
        registration_candidate=target_plate,
        confidence=0.95,
        match_score=0.95,
        match_class=MatchClass.EXACT,
        created_at=datetime.now(timezone.utc),
        event_time_utc=datetime.now(timezone.utc),
        event_time_source="SOURCE_WALLCLOCK",
        event_time_quality="HIGH"
    ))

    client = TestClient(app)
    res = client.get(f"/api/v1/routes/{target_plate}/geojson")
    assert res.status_code == 200
    geojson = res.json()
    assert geojson["type"] == "FeatureCollection"
    assert "features" in geojson
    assert isinstance(geojson["features"], list)
    assert len(geojson["features"]) >= 1


def test_get_target_route_summary():
    client = TestClient(app)
    res = client.get("/api/v1/routes/GJ01NONEXISTENT/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["registration"] == "GJ01NONEXISTENT"
    assert data["status"] == "NO_ROUTE"
    assert data["sighting_count"] == 0


def test_route_report_escapes_spreadsheet_formula_cells():
    route_service = importlib.import_module("08_backend.services.route_service")
    assert route_service.RouteService._csv_cell("=HYPERLINK(\"bad\")").startswith("'")
    assert route_service.RouteService._csv_cell("  +1+1").startswith("'")
    assert route_service.RouteService._csv_cell("Junction A") == "Junction A"
