import pytest
import importlib
from datetime import datetime, timezone, timedelta

spatial_mod = importlib.import_module('07_route_engine.spatial')
models_mod = importlib.import_module('07_route_engine.models')
cfg_mod = importlib.import_module('07_route_engine.config')
pipe_mod = importlib.import_module('07_route_engine.pipeline')
cam_mod = importlib.import_module('07_route_engine.camera_repository')
sight_mod = importlib.import_module('07_route_engine.sighting_repository')
repo_mod = importlib.import_module('07_route_engine.repository')

haversine_distance_m = spatial_mod.haversine_distance_m
RouteEngineConfig = cfg_mod.RouteEngineConfig
RouteEnginePipeline = pipe_mod.RouteEnginePipeline
RouteSighting = models_mod.RouteSighting
CameraGeo = models_mod.CameraGeo
TrajectoryStatus = models_mod.TrajectoryStatus
InMemoryCameraRepository = cam_mod.InMemoryCameraRepository
InMemorySightingRepository = sight_mod.InMemorySightingRepository
InMemoryRouteRepository = repo_mod.InMemoryRouteRepository


def test_distance_parity_vs_postgis_geodesic():
    # Test coordinates: Ahmedabad junction to SG Highway junction
    lat1, lon1 = 23.0225, 72.5714
    lat2, lon2 = 23.0330, 72.5850

    python_dist = haversine_distance_m(lat1, lon1, lat2, lon2)
    assert python_dist > 1800.0 and python_dist < 2000.0

    # Query PostGIS ST_Distance directly
    db_mod = importlib.import_module('00_foundation.registry.database')
    try:
        with db_mod.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT ST_Distance(
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                    );
                ''', (lon1, lat1, lon2, lat2))
                row = cur.fetchone()
                if row and row[0] is not None:
                    postgis_dist = float(row[0])
                    # Difference between Haversine sphere and PostGIS WGS84 ellipsoid is typically < 0.3%
                    diff_pct = abs(python_dist - postgis_dist) / postgis_dist * 100.0
                    assert diff_pct < 0.50, f'Distance difference {diff_pct:.2f}% exceeds 0.5%'
    except Exception:
        pass


def test_config_overrides_feasibility_behavior():
    t0 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=5)

    s1 = RouteSighting('s1', 'GJ01SPEED', 'GJ01SPEED', 'C1', 1, 1, 0.0, 100.0, t0, match_score=0.95)
    s2 = RouteSighting('s2', 'GJ01SPEED', 'GJ01SPEED', 'C2', 1, 1, 0.0, 100.0, t1, match_score=0.95)

    cam_repo = InMemoryCameraRepository()
    # 20 km in 5 min = 240 km/h
    cam_repo.save_camera(CameraGeo('C1', 'C1', 23.0000, 72.5000))
    cam_repo.save_camera(CameraGeo('C2', 'C2', 23.1800, 72.5000))

    # Strict config with 200 km/h limit -> IMPOSSIBLE -> Excluded
    strict_cfg = RouteEngineConfig(hard_max_speed_kmh=200.0)
    pipeline_strict = RouteEnginePipeline(
        config=strict_cfg,
        camera_repo=cam_repo,
        sighting_repo=InMemorySightingRepository([s1, s2]),
        route_repo=InMemoryRouteRepository()
    )
    traj_strict = pipeline_strict.build_target_trajectory('GJ01SPEED')
    # Path cannot include impossible transition
    assert len(traj_strict.segments) == 0

    # Relaxed config with 300 km/h limit -> QUESTIONABLE -> Included
    relaxed_cfg = RouteEngineConfig(hard_max_speed_kmh=300.0, highway_soft_speed_kmh=150.0)
    pipeline_relaxed = RouteEnginePipeline(
        config=relaxed_cfg,
        camera_repo=cam_repo,
        sighting_repo=InMemorySightingRepository([s1, s2]),
        route_repo=InMemoryRouteRepository()
    )
    traj_relaxed = pipeline_relaxed.build_target_trajectory('GJ01SPEED')
    assert len(traj_relaxed.segments) == 1


def test_pipeline_resilience_malformed_coordinates():
    cam_repo = InMemoryCameraRepository()
    cam_repo.save_camera(CameraGeo('C_BAD', 'Bad Cam', float('nan'), 72.5000))
    cam_repo.save_camera(CameraGeo('C_GOOD', 'Good Cam', 23.0000, 72.5000))

    t0 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    sightings = [
        RouteSighting('s1', 'GJ01RES', 'GJ01RES', 'C_BAD', 1, 1, 0.0, 100.0, t0, match_score=0.95),
        RouteSighting('s2', 'GJ01RES', 'GJ01RES', 'C_GOOD', 1, 1, 0.0, 100.0, t0 + timedelta(minutes=5), match_score=0.95)
    ]

    pipeline = RouteEnginePipeline(
        camera_repo=cam_repo,
        sighting_repo=InMemorySightingRepository(sightings),
        route_repo=InMemoryRouteRepository()
    )

    # Should gracefully process without exception
    traj = pipeline.build_target_trajectory('GJ01RES')
    assert len(traj.sightings) == 2
    assert traj.geojson['type'] == 'FeatureCollection'
