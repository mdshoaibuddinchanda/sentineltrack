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
LocationQuality = models_mod.LocationQuality
InMemoryCameraRepository = cam_mod.InMemoryCameraRepository
InMemorySightingRepository = sight_mod.InMemorySightingRepository
InMemoryRouteRepository = repo_mod.InMemoryRouteRepository


def test_complex_route_with_competing_branches():
    # Setup camera network (Ahmedabad Ring Road)
    cams = {
        'C1': CameraGeo('C1', 'SG Highway Entry', 23.0300, 72.5000),
        'C2A': CameraGeo('C2A', 'Pakwan Junction', 23.0450, 72.5150),
        'C2B': CameraGeo('C2B', 'Satellite Road', 23.0250, 72.5250),
        'C3': CameraGeo('C3', 'Thaltej Crossroad', 23.0600, 72.5250),
        'C4': CameraGeo('C4', 'Sola Bridge', 23.0800, 72.5350)
    }
    cam_repo = InMemoryCameraRepository()
    for c in cams.values():
        cam_repo.save_camera(c)

    # Sightings: Vehicle travels C1 -> C2A -> C3 -> C4 (Branch A, match scores ~0.95)
    # Spurious low-score sighting at C2B at the same time
    t0 = datetime(2026, 8, 28, 11, 0, 0, tzinfo=timezone.utc)
    sightings = [
        RouteSighting('s1', 'GJ01XY9999', 'GJ01XY9999', 'C1', 1, 1, 0.0, 100.0, t0, match_score=0.98),
        RouteSighting('s2a', 'GJ01XY9999', 'GJ01XY9999', 'C2A', 1, 1, 0.0, 100.0, t0 + timedelta(minutes=5), match_score=0.96),
        RouteSighting('s2b', 'GJ01XY9999', 'GJ01XY9999', 'C2B', 1, 1, 0.0, 100.0, t0 + timedelta(minutes=5), match_score=0.62), # Weaker match
        RouteSighting('s3', 'GJ01XY9999', 'GJ01XY9999', 'C3', 1, 1, 0.0, 100.0, t0 + timedelta(minutes=10), match_score=0.94),
        RouteSighting('s4', 'GJ01XY9999', 'GJ01XY9999', 'C4', 1, 1, 0.0, 100.0, t0 + timedelta(minutes=18), match_score=0.97),
    ]

    pipeline = RouteEnginePipeline(
        camera_repo=cam_repo,
        sighting_repo=InMemorySightingRepository(sightings),
        route_repo=InMemoryRouteRepository()
    )

    traj = pipeline.build_target_trajectory('GJ01XY9999')
    assert traj.status == TrajectoryStatus.CONFIRMED_SEQUENCE
    assert len(traj.sightings) == 4
    # Selected path must include C2A and exclude C2B
    assert [s.camera_id for s in traj.sightings] == ['C1', 'C2A', 'C3', 'C4']
    assert traj.total_lower_bound_distance_m > 6000.0


def test_route_with_loopback_revisit():
    # Vehicle visits Camera A -> Camera B -> Camera A (return trip after 30 min)
    cam_repo = InMemoryCameraRepository()
    cam_repo.save_camera(CameraGeo('CA', 'Station Entry', 23.0200, 72.5700))
    cam_repo.save_camera(CameraGeo('CB', 'Airport Road', 23.0700, 72.6200))

    t0 = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    sightings = [
        RouteSighting('s1', 'GJ01ZZ0001', 'GJ01ZZ0001', 'CA', 1, 1, 0.0, 100.0, t0, match_score=0.95),
        RouteSighting('s2', 'GJ01ZZ0001', 'GJ01ZZ0001', 'CB', 1, 1, 0.0, 100.0, t0 + timedelta(minutes=15), match_score=0.94),
        RouteSighting('s3', 'GJ01ZZ0001', 'GJ01ZZ0001', 'CA', 1, 1, 0.0, 100.0, t0 + timedelta(minutes=45), match_score=0.96),
    ]

    pipeline = RouteEnginePipeline(
        camera_repo=cam_repo,
        sighting_repo=InMemorySightingRepository(sightings),
        route_repo=InMemoryRouteRepository()
    )

    traj = pipeline.build_target_trajectory('GJ01ZZ0001')
    assert traj.status == TrajectoryStatus.CONFIRMED_SEQUENCE
    assert len(traj.sightings) == 3
    assert [s.camera_id for s in traj.sightings] == ['CA', 'CB', 'CA']
    assert len(traj.segments) == 2


def test_route_with_missing_camera_geolocation():
    cam_repo = InMemoryCameraRepository()
    cam_repo.save_camera(CameraGeo('C_GEO', 'Known Cam', 23.0200, 72.5700, location_quality=LocationQuality.VERIFIED))
    cam_repo.save_camera(CameraGeo('C_NO_GEO', 'Unknown Location Cam', None, None, location_quality=LocationQuality.UNKNOWN))

    t0 = datetime(2026, 8, 28, 14, 0, 0, tzinfo=timezone.utc)
    sightings = [
        RouteSighting('s1', 'GJ01NO_GEO', 'GJ01NO_GEO', 'C_GEO', 1, 1, 0.0, 100.0, t0, match_score=0.95),
        RouteSighting('s2', 'GJ01NO_GEO', 'GJ01NO_GEO', 'C_NO_GEO', 1, 1, 0.0, 100.0, t0 + timedelta(minutes=10), match_score=0.92),
    ]

    pipeline = RouteEnginePipeline(
        camera_repo=cam_repo,
        sighting_repo=InMemorySightingRepository(sightings),
        route_repo=InMemoryRouteRepository()
    )

    traj = pipeline.build_target_trajectory('GJ01NO_GEO')
    assert len(traj.sightings) == 2
    # Warning must be generated for unknown camera location
    assert any('unknown' in w.lower() for w in traj.warnings)
