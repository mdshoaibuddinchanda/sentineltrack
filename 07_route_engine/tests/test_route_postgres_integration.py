import pytest
import importlib
from datetime import datetime, timezone, timedelta

models_mod = importlib.import_module('07_route_engine.models')
cam_mod = importlib.import_module('07_route_engine.camera_repository')
sight_mod = importlib.import_module('07_route_engine.sighting_repository')
repo_mod = importlib.import_module('07_route_engine.repository')
pipe_mod = importlib.import_module('07_route_engine.pipeline')

CameraGeo = models_mod.CameraGeo
LocationQuality = models_mod.LocationQuality
RouteSighting = models_mod.RouteSighting
TrajectoryStatus = models_mod.TrajectoryStatus
PostgresCameraRepository = cam_mod.PostgresCameraRepository
PostgresRouteRepository = repo_mod.PostgresRouteRepository
InMemorySightingRepository = sight_mod.InMemorySightingRepository
RouteEnginePipeline = pipe_mod.RouteEnginePipeline


def test_postgis_camera_and_route_integration():
    cam_repo = PostgresCameraRepository()

    # 1. Insert/Update test cameras with PostGIS geography
    cam1 = CameraGeo('postgis_test_cam1', 'Junction Alpha', 23.0200, 72.5700, location_quality=LocationQuality.VERIFIED)
    cam2 = CameraGeo('postgis_test_cam2', 'Junction Beta', 23.0400, 72.5800, location_quality=LocationQuality.VERIFIED)

    assert cam_repo.save_camera(cam1) is True
    assert cam_repo.save_camera(cam2) is True

    # 2. Query nearby cameras using PostGIS ST_DWithin
    nearby = cam_repo.get_nearby_cameras(23.0200, 72.5700, radius_m=5000.0)
    assert any(c.camera_id == 'postgis_test_cam1' for c in nearby)

    # 3. Test Pipeline Trajectory Persistence
    t1 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 28, 10, 8, 0, tzinfo=timezone.utc)

    s1 = RouteSighting('s_pg_1', 'TEST_P7_POSTGIS', 'TEST_P7_POSTGIS', 'postgis_test_cam1', 1, 1, 0.0, 100.0, t1, latitude=23.0200, longitude=72.5700, match_score=0.98)
    s2 = RouteSighting('s_pg_2', 'TEST_P7_POSTGIS', 'TEST_P7_POSTGIS', 'postgis_test_cam2', 1, 1, 0.0, 100.0, t2, latitude=23.0400, longitude=72.5800, match_score=0.95)

    sighting_repo = InMemorySightingRepository([s1, s2])
    route_repo = PostgresRouteRepository()

    pipeline = RouteEnginePipeline(
        camera_repo=cam_repo,
        sighting_repo=sighting_repo,
        route_repo=route_repo
    )

    traj = pipeline.build_target_trajectory('TEST_P7_POSTGIS', persist=True)
    assert traj.status == TrajectoryStatus.CONFIRMED_SEQUENCE
    assert len(traj.sightings) == 2
    assert len(traj.segments) == 1

    # Read back from database
    latest = route_repo.get_latest_trajectory_run('TEST_P7_POSTGIS')
    assert latest is not None
    assert latest.target_id == 'TEST_P7_POSTGIS'
    assert latest.trajectory_confidence == traj.trajectory_confidence
