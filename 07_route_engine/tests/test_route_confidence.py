import importlib
from datetime import datetime, timezone

conf_mod = importlib.import_module('07_route_engine.confidence')
models_mod = importlib.import_module('07_route_engine.models')

evaluate_trajectory_confidence_and_reasons = conf_mod.evaluate_trajectory_confidence_and_reasons
RouteSighting = models_mod.RouteSighting
RouteSegment = models_mod.RouteSegment
TrajectoryStatus = models_mod.TrajectoryStatus
FeasibilityClass = models_mod.FeasibilityClass
TimeQuality = models_mod.TimeQuality
LocationQuality = models_mod.LocationQuality


def test_confidence_empty():
    conf, reasons, warns = evaluate_trajectory_confidence_and_reasons([], [], TrajectoryStatus.NO_ROUTE)
    assert conf == 0.0
    assert len(reasons) > 0


def test_confidence_high_quality_trajectory():
    now = datetime.now(timezone.utc)
    s1 = RouteSighting('s1', 'T1', 'GJ01AB1234', 'c1', 1, 1, 0.0, 100.0, now, match_score=0.98, time_quality=TimeQuality.HIGH, location_quality=LocationQuality.VERIFIED)
    s2 = RouteSighting('s2', 'T1', 'GJ01AB1234', 'c2', 1, 1, 0.0, 100.0, now, match_score=0.96, time_quality=TimeQuality.HIGH, location_quality=LocationQuality.VERIFIED)

    seg = RouteSegment('s1', 's2', 'c1', 'c2', now, now, 1000.0, 60.0, 60.0, FeasibilityClass.FEASIBLE, 1.0)
    conf, reasons, warns = evaluate_trajectory_confidence_and_reasons([s1, s2], [seg], TrajectoryStatus.CONFIRMED_SEQUENCE)

    assert conf >= 0.90
    assert any('verified' in r.lower() for r in reasons)


def test_confidence_penalized_for_low_time_quality():
    now = datetime.now(timezone.utc)
    s1 = RouteSighting('s1', 'T1', 'GJ01AB1234', 'c1', 1, 1, 0.0, 100.0, now, match_score=0.98, time_quality=TimeQuality.LOW, location_quality=LocationQuality.VERIFIED)
    s2 = RouteSighting('s2', 'T1', 'GJ01AB1234', 'c2', 1, 1, 0.0, 100.0, now, match_score=0.96, time_quality=TimeQuality.LOW, location_quality=LocationQuality.VERIFIED)

    seg = RouteSegment('s1', 's2', 'c1', 'c2', now, now, 1000.0, 60.0, 60.0, FeasibilityClass.FEASIBLE, 0.85)
    conf, reasons, warns = evaluate_trajectory_confidence_and_reasons([s1, s2], [seg], TrajectoryStatus.PLAUSIBLE_SEQUENCE)

    assert any('fallback' in w.lower() for w in warns)
