import importlib
from datetime import datetime, timezone

models_mod = importlib.import_module('07_route_engine.models')
CameraGeo = models_mod.CameraGeo
LocationQuality = models_mod.LocationQuality
TimeSource = models_mod.TimeSource
TimeQuality = models_mod.TimeQuality
EventTimeInfo = models_mod.EventTimeInfo
RouteSighting = models_mod.RouteSighting
RouteSegment = models_mod.RouteSegment
FeasibilityClass = models_mod.FeasibilityClass
TargetTrajectory = models_mod.TargetTrajectory
TrajectoryStatus = models_mod.TrajectoryStatus
TrajectorySummary = models_mod.TrajectorySummary


def test_camera_geo_validation():
    valid_cam = CameraGeo(
        camera_id='cam_01',
        latitude=23.0225,
        longitude=72.5714,
        azimuth=90.0,
        location_quality=LocationQuality.VERIFIED
    )
    assert valid_cam.has_valid_coordinates is True

    invalid_cam = CameraGeo(
        camera_id='cam_02',
        latitude=120.0,  # Out of range
        longitude=72.5714
    )
    assert invalid_cam.has_valid_coordinates is False

    none_cam = CameraGeo(camera_id='cam_03')
    assert none_cam.has_valid_coordinates is False


def test_event_time_info_creation():
    now = datetime.now(timezone.utc)
    eti = EventTimeInfo(
        source_pts_ms=120500.0,
        stream_epoch=1,
        event_time_utc=now,
        time_source=TimeSource.PTS_ANCHORED_ESTIMATE,
        time_quality=TimeQuality.MEDIUM
    )
    assert eti.source_pts_ms == 120500.0
    assert eti.stream_epoch == 1
    assert eti.time_source == TimeSource.PTS_ANCHORED_ESTIMATE
    assert eti.time_quality == TimeQuality.MEDIUM


def test_route_sighting_model():
    now = datetime.now(timezone.utc)
    s = RouteSighting(
        sighting_id='s_101',
        target_id='GJ01AB1234',
        registration_candidate='GJ01AB1234',
        camera_id='cam_junction_1',
        stream_epoch=1,
        track_id=42,
        first_pts_ms=1000.0,
        last_pts_ms=2500.0,
        event_time_utc=now,
        latitude=23.0225,
        longitude=72.5714,
        match_score=0.98,
        match_class='EXACT'
    )
    assert s.sighting_id == 's_101'
    assert s.match_score == 0.98
    assert s.latitude == 23.0225


def test_route_segment_model():
    now = datetime.now(timezone.utc)
    seg = RouteSegment(
        from_sighting_id='s_1',
        to_sighting_id='s_2',
        from_camera_id='cam_1',
        to_camera_id='cam_2',
        from_time_utc=now,
        to_time_utc=now,
        distance_lower_bound_m=1500.0,
        delta_seconds=60.0,
        minimum_required_speed_kmh=90.0,
        feasibility=FeasibilityClass.FEASIBLE,
        segment_score=0.95
    )
    assert seg.distance_lower_bound_m == 1500.0
    assert seg.minimum_required_speed_kmh == 90.0
    assert seg.feasibility == FeasibilityClass.FEASIBLE


def test_trajectory_summary_model():
    now = datetime.now(timezone.utc)
    summary = TrajectorySummary(
        target_id='GJ01AB1234',
        registration='GJ01AB1234',
        status=TrajectoryStatus.CONFIRMED_SEQUENCE,
        trajectory_confidence=0.94,
        first_seen_utc=now,
        last_seen_utc=now,
        sighting_count=4,
        camera_count=3,
        total_lower_bound_distance_km=12.5,
        minimum_average_speed_kmh=55.0,
        warnings_count=0
    )
    assert summary.sighting_count == 4
    assert summary.camera_count == 3
    assert summary.trajectory_confidence == 0.94
