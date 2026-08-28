import importlib
from datetime import datetime, timezone, timedelta

traj_mod = importlib.import_module('07_route_engine.trajectory')
models_mod = importlib.import_module('07_route_engine.models')
cfg_mod = importlib.import_module('07_route_engine.config')

solve_best_trajectory_dag = traj_mod.solve_best_trajectory_dag
collapse_same_camera_dwell_sightings = traj_mod.collapse_same_camera_dwell_sightings
compute_node_score = traj_mod.compute_node_score
RouteSighting = models_mod.RouteSighting
CameraGeo = models_mod.CameraGeo
TrajectoryStatus = models_mod.TrajectoryStatus
LocationQuality = models_mod.LocationQuality
TimeQuality = models_mod.TimeQuality
RouteEngineConfig = cfg_mod.RouteEngineConfig


def test_trajectory_empty_sightings():
    sightings, segments, status, conf, alts, warns = solve_best_trajectory_dag([], {})
    assert status == TrajectoryStatus.NO_ROUTE
    assert len(sightings) == 0
    assert conf == 0.0


def test_trajectory_single_sighting():
    now = datetime.now(timezone.utc)
    s = RouteSighting('s1', 'T1', 'GJ01AB1234', 'cam1', 1, 1, 0.0, 100.0, now, match_score=0.95)
    sightings, segments, status, conf, alts, warns = solve_best_trajectory_dag([s], {})
    assert status == TrajectoryStatus.SINGLE_SIGHTING
    assert len(sightings) == 1
    assert len(segments) == 0
    assert conf > 0.0


def test_trajectory_ordered_chronological_valid_route():
    t1 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 28, 10, 10, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 8, 28, 10, 20, 0, tzinfo=timezone.utc)

    # Input out of chronological order
    s1 = RouteSighting('s1', 'T1', 'GJ01AB1234', 'cam1', 1, 1, 1000.0, 2000.0, t1, match_score=0.98)
    s2 = RouteSighting('s2', 'T1', 'GJ01AB1234', 'cam2', 1, 1, 500.0, 1500.0, t2, match_score=0.95)  # Note stream pts is lower!
    s3 = RouteSighting('s3', 'T1', 'GJ01AB1234', 'cam3', 1, 1, 8000.0, 9000.0, t3, match_score=0.92)

    cams = {
        'cam1': CameraGeo('cam1', latitude=23.0200, longitude=72.5700),
        'cam2': CameraGeo('cam2', latitude=23.0500, longitude=72.5800),
        'cam3': CameraGeo('cam3', latitude=23.0800, longitude=72.5900)
    }

    # Pass in shuffled order
    sightings, segments, status, conf, alts, warns = solve_best_trajectory_dag([s3, s1, s2], cams)
    assert status == TrajectoryStatus.CONFIRMED_SEQUENCE
    assert len(sightings) == 3
    assert [s.sighting_id for s in sightings] == ['s1', 's2', 's3']
    assert len(segments) == 2


def test_trajectory_filters_impossible_jump_candidate():
    t1 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 28, 10, 10, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 8, 28, 10, 20, 0, tzinfo=timezone.utc)

    # Normal valid path
    s1 = RouteSighting('s1', 'T1', 'GJ01AB1234', 'cam1', 1, 1, 0.0, 100.0, t1, match_score=0.95)
    s2 = RouteSighting('s2', 'T1', 'GJ01AB1234', 'cam2', 1, 1, 0.0, 100.0, t2, match_score=0.92)
    s3 = RouteSighting('s3', 'T1', 'GJ01AB1234', 'cam3', 1, 1, 0.0, 100.0, t3, match_score=0.96)

    # Impossible jump candidate at 10:05 in another distant city (500 km away)
    t_fake = datetime(2026, 8, 28, 10, 5, 0, tzinfo=timezone.utc)
    s_fake = RouteSighting('s_fake', 'T1', 'GJ01AB1234', 'cam_far', 1, 1, 0.0, 100.0, t_fake, match_score=0.75)

    cams = {
        'cam1': CameraGeo('cam1', latitude=23.0200, longitude=72.5700),
        'cam2': CameraGeo('cam2', latitude=23.0500, longitude=72.5800),
        'cam3': CameraGeo('cam3', latitude=23.0800, longitude=72.5900),
        'cam_far': CameraGeo('cam_far', latitude=28.7041, longitude=77.1025)  # Delhi ~800 km away
    }

    sightings, segments, status, conf, alts, warns = solve_best_trajectory_dag([s1, s_fake, s2, s3], cams)
    assert 's_fake' not in [s.sighting_id for s in sightings]
    assert [s.sighting_id for s in sightings] == ['s1', 's2', 's3']


def test_collapse_same_camera_dwell():
    t1 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 28, 10, 0, 10, tzinfo=timezone.utc)
    t3 = datetime(2026, 8, 28, 10, 0, 20, tzinfo=timezone.utc)

    s1 = RouteSighting('s1', 'T1', 'GJ01AB1234', 'cam1', 1, 1, 0.0, 1000.0, t1, match_score=0.85, support_count=1)
    s2 = RouteSighting('s2', 'T1', 'GJ01AB1234', 'cam1', 1, 1, 1000.0, 2000.0, t2, match_score=0.95, support_count=2)
    s3 = RouteSighting('s3', 'T1', 'GJ01AB1234', 'cam1', 1, 1, 2000.0, 3000.0, t3, match_score=0.90, support_count=1)

    collapsed = collapse_same_camera_dwell_sightings([s1, s2, s3])
    assert len(collapsed) == 1
    assert collapsed[0].match_score == 0.95
    assert collapsed[0].support_count == 4
    assert collapsed[0].last_pts_ms == 3000.0
