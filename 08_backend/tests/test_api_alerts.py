import uuid
import pytest
import importlib
from datetime import datetime, timezone
from fastapi.testclient import TestClient

backend_app = importlib.import_module("08_backend.app")
p5_models = importlib.import_module("05_target_matching.models")
p5_repo = importlib.import_module("05_target_matching.repository")

app = backend_app.app
Alert = p5_models.Alert
MatchClass = p5_models.MatchClass
AlertSeverity = p5_models.AlertSeverity
PostgresTargetMatchingRepository = p5_repo.PostgresTargetMatchingRepository


def test_list_alerts_and_get_by_id():
    repo = PostgresTargetMatchingRepository()
    alert_id = str(uuid.uuid4())
    w_id = str(uuid.uuid4())
    s_id = str(uuid.uuid4())
    reg = f"GJ01ALT{uuid.uuid4().hex[:4].upper()}"

    # First insert prerequisite watchlist entry and sighting
    repo.save_watchlist_entry(p5_models.WatchlistEntry(
        watchlist_id=w_id,
        registration=reg,
        normalized_registration=reg,
        priority=p5_models.WatchlistPriority.HIGH
    ))
    repo.save_sighting(p5_models.Sighting(
        sighting_id=s_id,
        camera_id="cam_alert_test",
        stream_epoch=1,
        track_id=1,
        first_pts_ms=0.0,
        last_pts_ms=100.0,
        registration_candidate=reg,
        confidence=0.98,
        match_score=1.0,
        match_class=MatchClass.EXACT
    ))

    alert = Alert(
        alert_id=alert_id,
        watchlist_id=w_id,
        sighting_id=s_id,
        camera_id="cam_alert_test",
        stream_epoch=1,
        track_id=1,
        registration=reg,
        match_score=1.0,
        match_class=MatchClass.EXACT,
        severity=AlertSeverity.CRITICAL,
        created_at=datetime.now(timezone.utc),
        acknowledged=False,
        explanation=["Exact match with high-priority stolen vehicle watchlist."]
    )
    repo.save_alert(alert)

    client = TestClient(app)
    # 1. List alerts
    res_list = client.get("/api/v1/alerts?unacknowledged=true")
    assert res_list.status_code == 200
    data = res_list.json()
    assert any(a["alert_id"] == alert_id for a in data["items"])

    # 2. Get alert detail
    res_get = client.get(f"/api/v1/alerts/{alert_id}")
    assert res_get.status_code == 200
    assert res_get.json()["alert_id"] == alert_id
    assert res_get.json()["severity"] == "CRITICAL"


def test_acknowledge_alert_endpoint():
    repo = PostgresTargetMatchingRepository()
    alert_id = str(uuid.uuid4())
    w_id = str(uuid.uuid4())
    s_id = str(uuid.uuid4())
    reg = f"GJ01ACK{uuid.uuid4().hex[:4].upper()}"

    repo.save_watchlist_entry(p5_models.WatchlistEntry(
        watchlist_id=w_id,
        registration=reg,
        normalized_registration=reg,
        priority=p5_models.WatchlistPriority.NORMAL
    ))
    repo.save_sighting(p5_models.Sighting(
        sighting_id=s_id,
        camera_id="cam_ack_test",
        stream_epoch=1,
        track_id=1,
        first_pts_ms=0.0,
        last_pts_ms=100.0,
        registration_candidate=reg,
        confidence=0.98,
        match_score=1.0,
        match_class=MatchClass.EXACT
    ))

    alert = Alert(
        alert_id=alert_id,
        watchlist_id=w_id,
        sighting_id=s_id,
        camera_id="cam_ack_test",
        stream_epoch=1,
        track_id=1,
        registration=reg,
        match_score=1.0,
        match_class=MatchClass.EXACT,
        severity=AlertSeverity.HIGH,
        created_at=datetime.now(timezone.utc),
        acknowledged=False
    )
    repo.save_alert(alert)

    client = TestClient(app)
    ack_res = client.post(f"/api/v1/alerts/{alert_id}/ack", json={"acknowledged_by": "officer_402"})
    assert ack_res.status_code == 200
    data = ack_res.json()
    assert data["success"] is True
    assert data["alert_id"] == alert_id
    assert data["acknowledged"] is True
    assert data["acknowledged_by"] == "officer_402"
