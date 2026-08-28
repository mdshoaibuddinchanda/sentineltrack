import importlib
from datetime import datetime, timezone, timedelta

time_mod = importlib.import_module('07_route_engine.time_mapping')
models_mod = importlib.import_module('07_route_engine.models')

resolve_event_time_info = time_mod.resolve_event_time_info
compute_segment_time_delta = time_mod.compute_segment_time_delta
TimeSource = models_mod.TimeSource
TimeQuality = models_mod.TimeQuality
RouteSighting = models_mod.RouteSighting


def test_resolve_event_time_explicit_wallclock():
    now = datetime.now(timezone.utc)
    raw = {
        'first_pts_ms': 5000.0,
        'stream_epoch': 1,
        'event_time_utc': now.isoformat(),
        'event_time_source': 'SOURCE_WALLCLOCK',
        'event_time_quality': 'HIGH'
    }
    info = resolve_event_time_info(raw)
    assert info.time_source == TimeSource.SOURCE_WALLCLOCK
    assert info.time_quality == TimeQuality.HIGH
    assert abs((info.event_time_utc - now).total_seconds()) < 0.01


def test_resolve_event_time_anchored_pts():
    stream_start = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    raw = {
        'first_pts_ms': 60000.0,  # 60s
        'stream_epoch': 1,
        'created_at': datetime.now(timezone.utc)
    }
    info = resolve_event_time_info(raw, stream_start_utc=stream_start)
    assert info.time_source == TimeSource.PTS_ANCHORED_ESTIMATE
    assert info.time_quality == TimeQuality.MEDIUM
    expected_event = stream_start + timedelta(seconds=60)
    assert info.event_time_utc == expected_event


def test_resolve_event_time_db_fallback():
    now = datetime.now(timezone.utc)
    raw = {
        'first_pts_ms': 5000.0,
        'stream_epoch': 1,
        'created_at': now
    }
    info = resolve_event_time_info(raw)
    assert info.time_source == TimeSource.DB_PERSISTENCE_FALLBACK
    assert info.time_quality == TimeQuality.LOW
    assert info.event_time_utc == now


def test_compute_segment_time_delta_chronological():
    t1 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 28, 10, 5, 0, tzinfo=timezone.utc)
    s1 = RouteSighting('s1', 'T1', 'GJ01AB1234', 'cam1', 1, 1, 0.0, 100.0, t1)
    s2 = RouteSighting('s2', 'T1', 'GJ01AB1234', 'cam2', 1, 1, 0.0, 100.0, t2)

    delta, warn = compute_segment_time_delta(s1, s2)
    assert delta == 300.0
    assert warn is None


def test_compute_segment_time_delta_clock_skew():
    t1 = datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 28, 9, 59, 58, tzinfo=timezone.utc)  # -2s skew
    s1 = RouteSighting('s1', 'T1', 'GJ01AB1234', 'cam1', 1, 1, 0.0, 100.0, t1)
    s2 = RouteSighting('s2', 'T1', 'GJ01AB1234', 'cam2', 1, 1, 0.0, 100.0, t2)

    delta, warn = compute_segment_time_delta(s1, s2, clock_skew_tolerance_s=5.0)
    assert delta == 0.001
    assert warn is not None
    assert 'clock skew' in warn.lower()
