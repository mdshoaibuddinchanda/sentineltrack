import pytest
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
InMemoryCameraRepository = cam_mod.InMemoryCameraRepository
InMemorySightingRepository = sight_mod.InMemorySightingRepository
InMemoryRouteRepository = repo_mod.InMemoryRouteRepository


def test_sql_injection_and_whitespace_sanitization():
    cam_repo = InMemoryCameraRepository()
    cam_repo.save_camera(CameraGeo('C1', 'Cam 1', 23.0100, 72.5100))

    t0 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    sightings = [
        RouteSighting('s1', 'GJ01AB1234', 'GJ01AB1234', 'C1', 1, 1, 0.0, 100.0, t0, match_score=0.98),
    ]

    pipeline = RouteEnginePipeline(
        camera_repo=cam_repo,
        sighting_repo=InMemorySightingRepository(sightings),
        route_repo=InMemoryRouteRepository()
    )

    # Search with messy formatting / punctuation
    traj1 = pipeline.build_target_trajectory('  gj-01-ab-1234  ')
    assert traj1.registration == 'GJ01AB1234'
    assert len(traj1.sightings) == 1

    # Search with attempt at injection string
    traj2 = pipeline.build_target_trajectory("GJ01AB1234' OR '1'='1")
    assert len(traj2.sightings) == 0


def test_large_history_bounded_candidate_limit():
    cam_repo = InMemoryCameraRepository()
    cam_repo.save_camera(CameraGeo('C1', 'Cam 1', 23.0100, 72.5100))

    t0 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    # Generate 100 sightings
    sightings = [
        RouteSighting(f's_{i}', 'GJ01SCALE', 'GJ01SCALE', 'C1', 1, 1, 0.0, 100.0, t0 + timedelta(seconds=i*10), match_score=0.95)
        for i in range(100)
    ]

    # Configure max candidates to 20
    cfg = RouteEngineConfig(max_candidate_sightings=20, collapse_same_camera_dwell=False)
    pipeline = RouteEnginePipeline(
        config=cfg,
        camera_repo=cam_repo,
        sighting_repo=InMemorySightingRepository(sightings),
        route_repo=InMemoryRouteRepository()
    )

    traj = pipeline.build_target_trajectory('GJ01SCALE')
    assert len(traj.sightings) <= 20


def test_geojson_rfc_properties_and_coordinates():
    cam_repo = InMemoryCameraRepository()
    cam_repo.save_camera(CameraGeo('C1', 'Cam 1', 23.0100, 72.5100))
    cam_repo.save_camera(CameraGeo('C2', 'Cam 2', 23.0200, 72.5200))

    t0 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    sightings = [
        RouteSighting('s1', 'GJ01GEOJSON', 'GJ01GEOJSON', 'C1', 1, 1, 0.0, 100.0, t0, match_score=0.98),
        RouteSighting('s2', 'GJ01GEOJSON', 'GJ01GEOJSON', 'C2', 1, 1, 0.0, 100.0, t0 + timedelta(minutes=5), match_score=0.95),
    ]

    pipeline = RouteEnginePipeline(
        camera_repo=cam_repo,
        sighting_repo=InMemorySightingRepository(sightings),
        route_repo=InMemoryRouteRepository()
    )

    gj = pipeline.get_route_geojson('GJ01GEOJSON')
    assert 'metadata' in gj
    assert gj['metadata']['rfc_compliance'] == 'RFC-7946'
    assert gj['metadata']['coordinate_system'] == 'EPSG:4326 (WGS84)'
    assert gj['metadata']['target_registration'] == 'GJ01GEOJSON'


def test_explainability_structured_reasons():
    cam_repo = InMemoryCameraRepository()
    cam_repo.save_camera(CameraGeo('C1', 'Cam 1', 23.0100, 72.5100))
    cam_repo.save_camera(CameraGeo('C2', 'Cam 2', 23.0200, 72.5200))

    t0 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    sightings = [
        RouteSighting('s1', 'GJ01EXP', 'GJ01EXP', 'C1', 1, 1, 0.0, 100.0, t0, match_score=0.98),
        RouteSighting('s2', 'GJ01EXP', 'GJ01EXP', 'C2', 1, 1, 0.0, 100.0, t0 + timedelta(minutes=5), match_score=0.95),
    ]

    pipeline = RouteEnginePipeline(
        camera_repo=cam_repo,
        sighting_repo=InMemorySightingRepository(sightings),
        route_repo=InMemoryRouteRepository()
    )

    traj = pipeline.build_target_trajectory('GJ01EXP')
    assert len(traj.reasons) >= 3
    assert any('match score' in r.lower() for r in traj.reasons)
    assert any('verified' in r.lower() for r in traj.reasons)
    assert any('physically plausible' in r.lower() for r in traj.reasons)
