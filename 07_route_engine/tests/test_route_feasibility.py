import importlib
from datetime import datetime, timezone, timedelta

feas_mod = importlib.import_module('07_route_engine.feasibility')
models_mod = importlib.import_module('07_route_engine.models')
cfg_mod = importlib.import_module('07_route_engine.config')

evaluate_segment_feasibility = feas_mod.evaluate_segment_feasibility
RouteSighting = models_mod.RouteSighting
CameraGeo = models_mod.CameraGeo
FeasibilityClass = models_mod.FeasibilityClass
TimeQuality = models_mod.TimeQuality
LocationQuality = models_mod.LocationQuality
RouteEngineConfig = cfg_mod.RouteEngineConfig


def test_evaluate_feasibility_urban_feasible():
    t1 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 28, 10, 5, 0, tzinfo=timezone.utc)  # 5 min = 300s
    s1 = RouteSighting('s1', 'T1', 'GJ01AB1234', 'cam1', 1, 1, 0.0, 100.0, t1)
    s2 = RouteSighting('s2', 'T1', 'GJ01AB1234', 'cam2', 1, 1, 0.0, 100.0, t2)

    # 3 km in 5 min = 36 km/h -> Feasible
    cam1 = CameraGeo('cam1', latitude=23.0225, longitude=72.5714)
    cam2 = CameraGeo('cam2', latitude=23.0450, longitude=72.5800)

    cfg = RouteEngineConfig()
    seg = evaluate_segment_feasibility(s1, s2, cam1, cam2, config=cfg)
    assert seg.feasibility == FeasibilityClass.FEASIBLE
    assert seg.minimum_required_speed_kmh < cfg.urban_soft_speed_kmh
    assert seg.segment_score >= 0.90


def test_evaluate_feasibility_impossible_speed():
    t1 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 28, 10, 1, 0, tzinfo=timezone.utc)  # 1 min = 60s
    s1 = RouteSighting('s1', 'T1', 'GJ01AB1234', 'cam1', 1, 1, 0.0, 100.0, t1)
    s2 = RouteSighting('s2', 'T1', 'GJ01AB1234', 'cam2', 1, 1, 0.0, 100.0, t2)

    # 50 km in 1 min = 3000 km/h -> IMPOSSIBLE
    cam1 = CameraGeo('cam1', latitude=23.0225, longitude=72.5714)
    cam2 = CameraGeo('cam2', latitude=23.5000, longitude=72.5714)

    cfg = RouteEngineConfig(hard_max_speed_kmh=220.0)
    seg = evaluate_segment_feasibility(s1, s2, cam1, cam2, config=cfg)
    assert seg.feasibility == FeasibilityClass.IMPOSSIBLE
    assert seg.minimum_required_speed_kmh > 220.0
    assert seg.segment_score == 0.0


def test_evaluate_feasibility_questionable_highway_speed():
    t1 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 28, 10, 10, 0, tzinfo=timezone.utc)  # 10 min = 600s
    s1 = RouteSighting('s1', 'T1', 'GJ01AB1234', 'cam1', 1, 1, 0.0, 100.0, t1)
    s2 = RouteSighting('s2', 'T1', 'GJ01AB1234', 'cam2', 1, 1, 0.0, 100.0, t2)

    # 25 km in 10 min = 150 km/h -> QUESTIONABLE (above 140 soft, below 220 hard)
    cam1 = CameraGeo('cam1', latitude=23.0225, longitude=72.5714)
    cam2 = CameraGeo('cam2', latitude=23.2500, longitude=72.5714)

    cfg = RouteEngineConfig(highway_soft_speed_kmh=140.0, hard_max_speed_kmh=220.0)
    seg = evaluate_segment_feasibility(s1, s2, cam1, cam2, config=cfg)
    assert seg.feasibility == FeasibilityClass.QUESTIONABLE
    assert 0.20 <= seg.segment_score < 1.0


def test_evaluate_feasibility_same_location_dwell():
    t1 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 28, 10, 2, 0, tzinfo=timezone.utc)
    s1 = RouteSighting('s1', 'T1', 'GJ01AB1234', 'cam1', 1, 1, 0.0, 100.0, t1)
    s2 = RouteSighting('s2', 'T1', 'GJ01AB1234', 'cam1', 1, 1, 0.0, 100.0, t2)

    cam1 = CameraGeo('cam1', latitude=23.0225, longitude=72.5714)
    seg = evaluate_segment_feasibility(s1, s2, cam1, cam1)
    assert seg.distance_lower_bound_m == 0.0
    assert seg.minimum_required_speed_kmh == 0.0
    assert seg.feasibility == FeasibilityClass.FEASIBLE
