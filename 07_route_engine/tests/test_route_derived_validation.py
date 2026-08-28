import importlib
from datetime import datetime, timezone, timedelta

pipe_mod = importlib.import_module('07_route_engine.pipeline')
models_mod = importlib.import_module('07_route_engine.models')
cam_mod = importlib.import_module('07_route_engine.camera_repository')
sight_mod = importlib.import_module('07_route_engine.sighting_repository')
repo_mod = importlib.import_module('07_route_engine.repository')
cfg_mod = importlib.import_module('07_route_engine.config')

RouteEnginePipeline = pipe_mod.RouteEnginePipeline
RouteEngineConfig = cfg_mod.RouteEngineConfig
RouteSighting = models_mod.RouteSighting
CameraGeo = models_mod.CameraGeo
TrajectoryStatus = models_mod.TrajectoryStatus
TimeQuality = models_mod.TimeQuality
LocationQuality = models_mod.LocationQuality
InMemoryCameraRepository = cam_mod.InMemoryCameraRepository
InMemorySightingRepository = sight_mod.InMemorySightingRepository
InMemoryRouteRepository = repo_mod.InMemoryRouteRepository


def test_derived_validation_large_temporal_gap():
    cam_repo = InMemoryCameraRepository()
    cam_repo.save_camera(CameraGeo('C1', 'North Toll', 23.0500, 72.5500))
    cam_repo.save_camera(CameraGeo('C2', 'South Toll', 22.9500, 72.5500))

    t0 = datetime(2026, 8, 28, 8, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(hours=6)  # 6 hour gap

    sightings = [
        RouteSighting('s1', 'GJ01GAP001', 'GJ01GAP001', 'C1', 1, 1, 0.0, 100.0, t0, match_score=0.98),
        RouteSighting('s2', 'GJ01GAP001', 'GJ01GAP001', 'C2', 1, 1, 0.0, 100.0, t1, match_score=0.97),
    ]

    pipeline = RouteEnginePipeline(
        camera_repo=cam_repo,
        sighting_repo=InMemorySightingRepository(sightings),
        route_repo=InMemoryRouteRepository()
    )

    traj = pipeline.build_target_trajectory('GJ01GAP001')
    assert len(traj.sightings) == 2
    assert any('large time gap' in w.lower() for w in traj.warnings)


def test_derived_validation_low_match_score_exclusion():
    cam_repo = InMemoryCameraRepository()
    cam_repo.save_camera(CameraGeo('C1', 'Cam 1', 23.0100, 72.5100))
    cam_repo.save_camera(CameraGeo('C2', 'Cam 2', 23.0300, 72.5300))

    t0 = datetime(2026, 8, 28, 9, 0, 0, tzinfo=timezone.utc)
    sightings = [
        RouteSighting('s1', 'GJ01LOW001', 'GJ01LOW001', 'C1', 1, 1, 0.0, 100.0, t0, match_score=0.95),
        RouteSighting('s2', 'GJ01LOW001', 'GJ01LOW001', 'C2', 1, 1, 0.0, 100.0, t0 + timedelta(minutes=5), match_score=0.45), # Below 0.60 threshold
    ]

    pipeline = RouteEnginePipeline(
        camera_repo=cam_repo,
        sighting_repo=InMemorySightingRepository(sightings),
        route_repo=InMemoryRouteRepository()
    )

    traj = pipeline.build_target_trajectory('GJ01LOW001')
    # Sighting s2 is filtered out due to score 0.45 < 0.60
    assert len(traj.sightings) == 1
    assert traj.status == TrajectoryStatus.SINGLE_SIGHTING
