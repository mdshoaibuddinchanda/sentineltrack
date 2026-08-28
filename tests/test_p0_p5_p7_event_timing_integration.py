import pytest
import importlib
import uuid
from datetime import datetime, timezone, timedelta

# Import modules via importlib to respect numbered package boundaries
p0_models = importlib.import_module('00_foundation.streams.models')
p4_models = importlib.import_module('04_plate_ocr.models')
p5_models = importlib.import_module('05_target_matching.models')
p5_pipe = importlib.import_module('05_target_matching.pipeline')
p5_repo = importlib.import_module('05_target_matching.repository')
p7_models = importlib.import_module('07_route_engine.models')
p7_sight_repo = importlib.import_module('07_route_engine.sighting_repository')
p7_cam_repo = importlib.import_module('07_route_engine.camera_repository')
p7_route_repo = importlib.import_module('07_route_engine.repository')
p7_pipe = importlib.import_module('07_route_engine.pipeline')

FramePacket = p0_models.FramePacket
TrackOCRResult = p4_models.TrackOCRResult
OCRHypothesis = p4_models.OCRHypothesis
Sighting = p5_models.Sighting
MatchClass = p5_models.MatchClass
PostgresTargetMatchingRepository = p5_repo.PostgresTargetMatchingRepository
PostgresSightingRepository = p7_sight_repo.PostgresSightingRepository
PostgresCameraRepository = p7_cam_repo.PostgresCameraRepository
PostgresRouteRepository = p7_route_repo.PostgresRouteRepository
CameraGeo = p7_models.CameraGeo
LocationQuality = p7_models.LocationQuality
RouteEnginePipeline = p7_pipe.RouteEnginePipeline
TrajectoryStatus = p7_models.TrajectoryStatus


def test_end_to_end_event_timing_propagation_and_ordering():
    """
    Critical Integration Test:
    Verifies that wall-clock event time propagates from P0 metadata -> P4 -> P5 (PostgreSQL) -> P7.
    Proves cross-camera trajectory ordering follows event_time_utc and NOT stream-local PTS.
    """
    # 1. Setup two cameras in PostgreSQL
    cam_repo = PostgresCameraRepository()
    cam_a = CameraGeo('cam_timetest_a', 'Highway Entry A', 23.0200, 72.5700, location_quality=LocationQuality.VERIFIED)
    cam_b = CameraGeo('cam_timetest_b', 'Highway Exit B', 23.0600, 72.5900, location_quality=LocationQuality.VERIFIED)
    cam_repo.save_camera(cam_a)
    cam_repo.save_camera(cam_b)

    # 2. Define distinct event times
    # Note: Cam A has HIGHER PTS (50000ms) at 10:00:00 UTC
    #       Cam B has LOWER PTS (2000ms) at 10:10:00 UTC
    t_a = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    t_b = datetime(2026, 8, 28, 10, 10, 0, tzinfo=timezone.utc)
    target_plate = f"GJ01TT{uuid.uuid4().hex[:6].upper()}"

    # 3. Simulate P4 TrackOCRResults with P0 timing metadata
    track_res_a = TrackOCRResult(
        camera_id='cam_timetest_a',
        track_id=101,
        stream_epoch=1,
        first_pts_ms=50000.0,
        last_pts_ms=52000.0,
        best_text=target_plate,
        confidence=0.98,
        support_count=5,
        total_hypotheses=5,
        status='RESOLVED'
    )
    track_res_a.event_time_utc = t_a
    track_res_a.event_time_source = 'PTS_ANCHORED_ESTIMATE'
    track_res_a.event_time_quality = 'MEDIUM'
    track_res_a.ingest_time_utc = t_a

    track_res_b = TrackOCRResult(
        camera_id='cam_timetest_b',
        track_id=202,
        stream_epoch=1,
        first_pts_ms=2000.0, # LOWER raw stream PTS!
        last_pts_ms=3000.0,
        best_text=target_plate,
        confidence=0.95,
        support_count=4,
        total_hypotheses=4,
        status='RESOLVED'
    )
    track_res_b.event_time_utc = t_b
    track_res_b.event_time_source = 'PTS_ANCHORED_ESTIMATE'
    track_res_b.event_time_quality = 'MEDIUM'
    track_res_b.ingest_time_utc = t_b

    # 4. Ingest through P5 Pipeline into PostgreSQL
    p5_repository = PostgresTargetMatchingRepository()
    p5_pipeline = p5_pipe.TargetMatchingPipeline(repository=p5_repository)
    p5_pipeline.watchlist_manager.add_entry(target_plate, priority=p5_models.WatchlistPriority.HIGH)

    # Insert both observations (in reverse order Cam B then Cam A)
    p5_pipeline.process_track_ocr_result(track_res_b)
    p5_pipeline.process_track_ocr_result(track_res_a)

    # 5. Retrieve via P7 Postgres Sighting Repository
    p7_sighting_repo = PostgresSightingRepository()
    retrieved_sightings = p7_sighting_repo.get_target_sightings(target_plate)

    assert len(retrieved_sightings) >= 2
    # Verify exact timing survived persistence
    s_a = next(s for s in retrieved_sightings if s.camera_id == 'cam_timetest_a')
    s_b = next(s for s in retrieved_sightings if s.camera_id == 'cam_timetest_b')

    assert abs((s_a.event_time_utc - t_a).total_seconds()) < 0.1
    assert s_a.time_source == p7_models.TimeSource.PTS_ANCHORED_ESTIMATE
    assert s_a.time_quality == p7_models.TimeQuality.MEDIUM

    assert abs((s_b.event_time_utc - t_b).total_seconds()) < 0.1
    assert s_b.time_source == p7_models.TimeSource.PTS_ANCHORED_ESTIMATE

    # 6. Run P7 Trajectory Engine Pipeline
    p7_pipeline = RouteEnginePipeline(
        camera_repo=cam_repo,
        sighting_repo=p7_sighting_repo,
        route_repo=PostgresRouteRepository()
    )

    traj = p7_pipeline.build_target_trajectory(target_plate, persist=True)

    # 7. Verify Trajectory correctly ordered: Cam A (10:00) -> Cam B (10:10)
    # Even though Cam B had smaller PTS (2000 vs 50000)!
    assert traj.status == TrajectoryStatus.CONFIRMED_SEQUENCE
    assert len(traj.sightings) == 2
    assert traj.sightings[0].camera_id == 'cam_timetest_a'
    assert traj.sightings[1].camera_id == 'cam_timetest_b'
    assert len(traj.segments) == 1
    assert abs(traj.segments[0].delta_seconds - 600.0) < 1.0  # 10 minutes
    assert traj.segments[0].feasibility == p7_models.FeasibilityClass.FEASIBLE
