import importlib
from datetime import datetime, timezone, timedelta

repo_mod = importlib.import_module('07_route_engine.repository')
models_mod = importlib.import_module('07_route_engine.models')

InMemoryRouteRepository = repo_mod.InMemoryRouteRepository
TargetTrajectory = models_mod.TargetTrajectory
TrajectoryStatus = models_mod.TrajectoryStatus
RouteSighting = models_mod.RouteSighting
RouteSegment = models_mod.RouteSegment
FeasibilityClass = models_mod.FeasibilityClass


def test_in_memory_route_repository_crud():
    repo = InMemoryRouteRepository()
    now = datetime.now(timezone.utc)

    traj = TargetTrajectory(
        target_id='GJ01AB9999',
        registration='GJ01AB9999',
        sightings=[],
        segments=[],
        trajectory_confidence=0.95,
        status=TrajectoryStatus.CONFIRMED_SEQUENCE,
        start_time_utc=now,
        end_time_utc=now + timedelta(minutes=10),
        duration_seconds=600.0,
        total_lower_bound_distance_m=5000.0,
        minimum_average_speed_kmh=30.0,
        geojson={'type': 'FeatureCollection', 'features': []},
        reasons=['Verified path'],
        warnings=[]
    )

    route_id = repo.save_trajectory_run(traj)
    assert route_id is not None

    fetched = repo.get_trajectory_run(route_id)
    assert fetched is not None
    assert fetched.target_id == 'GJ01AB9999'
    assert fetched.trajectory_confidence == 0.95

    latest = repo.get_latest_trajectory_run('GJ01AB9999')
    assert latest is not None
    assert latest.target_id == 'GJ01AB9999'

    # Non-existent target
    assert repo.get_latest_trajectory_run('NONEXISTENT') is None
