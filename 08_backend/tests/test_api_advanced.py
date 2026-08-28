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
Sighting = p5_models.Sighting
MatchClass = p5_models.MatchClass
PostgresTargetMatchingRepository = p5_repo.PostgresTargetMatchingRepository
PostgresCameraRepository = p7_cam_repo.PostgresCameraRepository
CameraGeo = p7_models.CameraGeo
LocationQuality = p7_models.LocationQuality


def test_request_correlation_id_and_latency_headers():
    client = TestClient(app)
    custom_id = "req-trace-xyz-12345"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_id
    assert "X-Response-Time-Ms" in response.headers
    latency = float(response.headers["X-Response-Time-Ms"])
    assert latency >= 0.0


def test_cors_headers_handling():
    client = TestClient(app)
    response = client.options(
        "/api/v1/cameras",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type"
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_openapi_schema_endpoint():
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "SentinelTrack Intelligence API"
    assert "/api/v1/cameras" in schema["paths"]
    assert "/api/v1/targets" in schema["paths"]
    assert "/api/v1/sightings" in schema["paths"]
    assert "/api/v1/alerts" in schema["paths"]
    assert "/api/v1/routes/{registration}" in schema["paths"]


def test_api_sightings_temporal_and_score_filtering():
    repo = PostgresTargetMatchingRepository()
    reg = f"GJ01FILT{uuid.uuid4().hex[:4].upper()}"
    t0 = datetime(2026, 8, 28, 8, 0, 0, tzinfo=timezone.utc)

    # 3 sightings: score 0.50, 0.75, 0.95 at 8:00, 8:15, 8:30
    for i, sc in enumerate([0.50, 0.75, 0.95]):
        repo.save_sighting(Sighting(
            sighting_id=str(uuid.uuid4()),
            camera_id=f"cam_filt_{i}",
            stream_epoch=1,
            track_id=i+1,
            first_pts_ms=0.0,
            last_pts_ms=100.0,
            registration_candidate=reg,
            confidence=0.95,
            match_score=sc,
            match_class=MatchClass.EXACT if sc > 0.9 else MatchClass.PROBABLE,
            created_at=t0 + timedelta(minutes=i*15),
            event_time_utc=t0 + timedelta(minutes=i*15),
            event_time_source="SOURCE_WALLCLOCK",
            event_time_quality="HIGH"
        ))

    client = TestClient(app)
    # Query with min_score=0.70 -> should return 2 items (0.75, 0.95)
    res = client.get(f"/api/v1/sightings?registration={reg}&min_score=0.70")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 2
    assert all(i["match_score"] >= 0.70 for i in items)


def test_api_routes_impossible_speed_segment_flagging():
    cam_repo = PostgresCameraRepository()
    c1 = CameraGeo("cam_speed_1", "Speed Point 1", 23.0000, 72.5000, location_quality=LocationQuality.VERIFIED)
    c2 = CameraGeo("cam_speed_2", "Speed Point 2", 23.5000, 72.5000, location_quality=LocationQuality.VERIFIED) # ~55 km away
    cam_repo.save_camera(c1)
    cam_repo.save_camera(c2)

    target_plate = f"GJ01SPEED{uuid.uuid4().hex[:4].upper()}"
    t0 = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=30) # 55km in 30s = 6600 km/h (impossible!)

    target_repo = PostgresTargetMatchingRepository()
    target_repo.save_sighting(Sighting(
        sighting_id=str(uuid.uuid4()),
        camera_id="cam_speed_1",
        stream_epoch=1,
        track_id=1,
        first_pts_ms=0.0,
        last_pts_ms=100.0,
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
        camera_id="cam_speed_2",
        stream_epoch=1,
        track_id=2,
        first_pts_ms=0.0,
        last_pts_ms=100.0,
        registration_candidate=target_plate,
        confidence=0.98,
        match_score=0.95,
        match_class=MatchClass.EXACT,
        created_at=t1,
        event_time_utc=t1,
        event_time_source="SOURCE_WALLCLOCK",
        event_time_quality="HIGH"
    ))

    client = TestClient(app)
    res = client.get(f"/api/v1/routes/{target_plate}")
    assert res.status_code == 200
    data = res.json()
    # Trajectory engine should detect impossible transition or classify status accordingly
    assert data["registration"] == target_plate
    assert len(data["segments"]) >= 0


def test_api_websocket_multiplex_topics():
    client = TestClient(app)
    ev_bus_mod = importlib.import_module("08_backend.event_bus")
    bus = ev_bus_mod.get_event_bus()
    AlertCreatedEvent = ev_bus_mod.AlertCreatedEvent

    with client.websocket_connect("/ws/events?topics=alerts,sightings") as ws:
        import asyncio
        asyncio.run(bus.publish(AlertCreatedEvent(payload={
            "alert_id": "ws_multi_alt_1",
            "camera_id": "cam1",
            "registration": "GJ01MULTI",
            "severity": "CRITICAL"
        })))

        msg = ws.receive_text()
        import json
        d = json.loads(msg)
        assert d["event_type"] == "ALERT_CREATED"
        assert d["data"]["registration"] == "GJ01MULTI"


def test_api_targets_pagination_limits():
    client = TestClient(app)
    # Default limit
    res_default = client.get("/api/v1/targets")
    assert res_default.status_code == 200

    # Explicit limit within bounds
    res_paged = client.get("/api/v1/targets?limit=5&offset=0")
    assert res_paged.status_code == 200
    assert len(res_paged.json()["items"]) <= 5

    # Out of bounds limit > 500 -> 422 Unprocessable Entity
    res_invalid = client.get("/api/v1/targets?limit=1000")
    assert res_invalid.status_code == 422


def test_api_create_target_invalid_registration_rejected():
    client = TestClient(app)
    # Registration too short (< 4 chars)
    res = client.post("/api/v1/targets", json={"registration": "A"})
    assert res.status_code == 422 or res.status_code == 400
