import importlib
from datetime import datetime, timezone, timedelta

models_mod = importlib.import_module('07_route_engine.models')
cam_mod = importlib.import_module('07_route_engine.camera_repository')
sight_mod = importlib.import_module('07_route_engine.sighting_repository')
repo_mod = importlib.import_module('07_route_engine.repository')
pipe_mod = importlib.import_module('07_route_engine.pipeline')
cfg_mod = importlib.import_module('07_route_engine.config')

RouteSighting = models_mod.RouteSighting
CameraGeo = models_mod.CameraGeo
TrajectoryStatus = models_mod.TrajectoryStatus
LocationQuality = models_mod.LocationQuality
TimeQuality = models_mod.TimeQuality
InMemoryCameraRepository = cam_mod.InMemoryCameraRepository
InMemorySightingRepository = sight_mod.InMemorySightingRepository
InMemoryRouteRepository = repo_mod.InMemoryRouteRepository
RouteEnginePipeline = pipe_mod.RouteEnginePipeline
RouteEngineConfig = cfg_mod.RouteEngineConfig


def test_pipeline_end_to_end_in_memory():
    # Set up cameras
    cam_repo = InMemoryCameraRepository()
    cam_repo.save_camera(CameraGeo('cam_1', 'Junction 1', 23.0200, 72.5700, location_quality=LocationQuality.VERIFIED))
    cam_repo.save_camera(CameraGeo('cam_2', 'Junction 2', 23.0400, 72.5800, location_quality=LocationQuality.VERIFIED))
    cam_repo.save_camera(CameraGeo('cam_3', 'Junction 3', 23.0600, 72.5900, location_quality=LocationQuality.VERIFIED))

    # Set up sightings
    t1 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 28, 10, 5, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 8, 28, 10, 12, 0, tzinfo=timezone.utc)

    s1 = RouteSighting('s1', 'GJ01AB1234', 'GJ01AB1234', 'cam_1', 1, 1, 0.0, 100.0, t1, match_score=0.98)
    s2 = RouteSighting('s2', 'GJ01AB1234', 'GJ01AB1234', 'cam_2', 1, 1, 0.0, 100.0, t2, match_score=0.95)
    s3 = RouteSighting('s3', 'GJ01AB1234', 'GJ01AB1234', 'cam_3', 1, 1, 0.0, 100.0, t3, match_score=0.92)

    sighting_repo = InMemorySightingRepository([s1, s2, s3])
    route_repo = InMemoryRouteRepository()

    pipeline = RouteEnginePipeline(
        camera_repo=cam_repo,
        sighting_repo=sighting_repo,
        route_repo=route_repo
    )

    # 1. Build trajectory
    traj = pipeline.build_target_trajectory('GJ01AB1234')
    assert traj.status == TrajectoryStatus.CONFIRMED_SEQUENCE
    assert len(traj.sightings) == 3
    assert len(traj.segments) == 2
    assert traj.total_lower_bound_distance_m > 4000.0
    assert traj.trajectory_confidence > 0.85

    # 2. Get GeoJSON
    gj = pipeline.get_route_geojson('GJ01AB1234')
    assert gj['type'] == 'FeatureCollection'
    assert len(gj['features']) == 4  # 3 Points + 1 LineString

    # 3. Summarize trajectory
    summary = pipeline.summarize_trajectory(traj)
    assert summary.sighting_count == 3
    assert summary.camera_count == 3
    assert summary.trajectory_confidence == traj.trajectory_confidence

    # 4. Nearby camera search
    nearby = pipeline.get_nearby_cameras(23.0200, 72.5700, radius_m=5000.0)
    assert len(nearby) >= 1
