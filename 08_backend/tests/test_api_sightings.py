import uuid
import pytest
import importlib
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

backend_app = importlib.import_module("08_backend.app")
p5_models = importlib.import_module("05_target_matching.models")
p5_repo = importlib.import_module("05_target_matching.repository")

app = backend_app.app
Sighting = p5_models.Sighting
MatchClass = p5_models.MatchClass
PostgresTargetMatchingRepository = p5_repo.PostgresTargetMatchingRepository


def test_list_sightings_with_filters():
    repo = PostgresTargetMatchingRepository()
    cam_id = "test_cam_sight_01"
    reg = f"GJ01SIGHT{uuid.uuid4().hex[:4].upper()}"
    t0 = datetime.now(timezone.utc)

    s = Sighting(
        sighting_id=str(uuid.uuid4()),
        camera_id=cam_id,
        stream_epoch=1,
        track_id=1,
        first_pts_ms=1000.0,
        last_pts_ms=2000.0,
        registration_candidate=reg,
        confidence=0.95,
        match_score=0.88,
        match_class=MatchClass.HIGH_PROBABILITY,
        created_at=t0,
        event_time_utc=t0,
        event_time_source="SOURCE_WALLCLOCK",
        event_time_quality="HIGH"
    )
    repo.save_sighting(s)

    client = TestClient(app)
    response = client.get(f"/api/v1/sightings?camera_id={cam_id}&min_score=0.80")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) >= 1
    item = next(i for i in data["items"] if i["sighting_id"] == s.sighting_id)
    assert item["camera_id"] == cam_id
    assert item["registration_candidate"] == reg
    assert item["event_time_source"] == "SOURCE_WALLCLOCK"


def test_get_vehicle_history_timeline():
    repo = PostgresTargetMatchingRepository()
    reg = f"GJ01HIST{uuid.uuid4().hex[:4].upper()}"
    t0 = datetime.now(timezone.utc)

    for i in range(3):
        s = Sighting(
            sighting_id=str(uuid.uuid4()),
            camera_id=f"test_cam_hist_{i}",
            stream_epoch=1,
            track_id=i+1,
            first_pts_ms=float(i*1000),
            last_pts_ms=float(i*1000 + 500),
            registration_candidate=reg,
            confidence=0.96,
            match_score=0.92,
            match_class=MatchClass.HIGH_PROBABILITY,
            created_at=t0 + timedelta(minutes=i*5),
            event_time_utc=t0 + timedelta(minutes=i*5),
            event_time_source="PTS_ANCHORED_ESTIMATE",
            event_time_quality="MEDIUM"
        )
        repo.save_sighting(s)

    client = TestClient(app)
    response = client.get(f"/api/v1/vehicles/{reg}/history")
    assert response.status_code == 200
    data = response.json()
    assert data["registration"] == reg
    assert data["total_sightings"] >= 3
    assert len(data["sightings"]) >= 3
