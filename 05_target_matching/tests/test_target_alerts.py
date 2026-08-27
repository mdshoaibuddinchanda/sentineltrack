import importlib
from datetime import datetime, timezone

alerts_mod = importlib.import_module('05_target_matching.alerts')
models_mod = importlib.import_module('05_target_matching.models')
scorer_mod = importlib.import_module('05_target_matching.scorer')

AlertManager = alerts_mod.AlertManager
calculate_alert_severity = alerts_mod.calculate_alert_severity
MatchClass = models_mod.MatchClass
WatchlistPriority = models_mod.WatchlistPriority
AlertSeverity = models_mod.AlertSeverity
WatchlistEntry = models_mod.WatchlistEntry
TargetMatchScorer = scorer_mod.TargetMatchScorer


def test_calculate_alert_severity():
    # Critical watchlist + exact match -> Critical alert
    sev_crit = calculate_alert_severity(WatchlistPriority.CRITICAL, MatchClass.EXACT, 1.0)
    assert sev_crit == AlertSeverity.CRITICAL

    # Normal watchlist + High probability match -> Medium alert
    sev_norm = calculate_alert_severity(WatchlistPriority.NORMAL, MatchClass.HIGH_PROBABILITY, 0.88)
    assert sev_norm == AlertSeverity.MEDIUM


def test_alert_manager_deduplication():
    am = AlertManager(cooldown_seconds=60.0)
    scorer = TargetMatchScorer()

    w_entry = WatchlistEntry(
        watchlist_id='w-001',
        registration='GJ01AB1234',
        normalized_registration='GJ01AB1234',
        priority=WatchlistPriority.HIGH
    )

    # Frame 1: Observation for track 42 on cam-1
    cand1 = scorer.score_match(
        target_id=w_entry.watchlist_id,
        target_registration=w_entry.normalized_registration,
        observed_registration='GJ01A81234',
        camera_id='cam-1',
        stream_epoch=1,
        track_id=42,
        ocr_confidence=0.92,
        crop_quality=0.85,
        multi_frame_support=2
    )

    alert1, is_new1, reason1 = am.process_match(cand1, w_entry, sighting_id='s-001')
    assert is_new1 is True
    assert alert1 is not None

    # Frame 2: Same vehicle track observed again with higher score
    cand2 = scorer.score_match(
        target_id=w_entry.watchlist_id,
        target_registration=w_entry.normalized_registration,
        observed_registration='GJ01AB1234',
        camera_id='cam-1',
        stream_epoch=1,
        track_id=42,
        multi_frame_support=3
    )

    alert2, is_new2, reason2 = am.process_match(cand2, w_entry, sighting_id='s-002')
    # Must NOT create a second duplicate alert, but update the existing one!
    assert is_new2 is False
    assert alert2.alert_id == alert1.alert_id
    assert alert2.match_score == 1.0


def test_alert_acknowledgment():
    am = AlertManager()
    scorer = TargetMatchScorer()
    w_entry = WatchlistEntry(
        watchlist_id='w-001',
        registration='GJ01AB1234',
        normalized_registration='GJ01AB1234'
    )
    cand = scorer.score_match(
        target_id=w_entry.watchlist_id,
        target_registration=w_entry.normalized_registration,
        observed_registration='GJ01AB1234'
    )
    alert, _, _ = am.process_match(cand, w_entry, sighting_id='s-001')

    assert alert.acknowledged is False
    ok = am.acknowledge_alert(alert.alert_id, acknowledged_by='officer_sharma')
    assert ok is True
    assert alert.acknowledged is True
    assert alert.acknowledged_by == 'officer_sharma'
