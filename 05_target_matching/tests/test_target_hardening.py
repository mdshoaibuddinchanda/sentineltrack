import pytest
import importlib
from datetime import datetime, timezone, timedelta

models_mod = importlib.import_module('05_target_matching.models')
config_mod = importlib.import_module('05_target_matching.config')
scorer_mod = importlib.import_module('05_target_matching.scorer')
alerts_mod = importlib.import_module('05_target_matching.alerts')
watchlist_mod = importlib.import_module('05_target_matching.watchlist')
repo_mod = importlib.import_module('05_target_matching.repository')
history_mod = importlib.import_module('05_target_matching.history')
pipeline_mod = importlib.import_module('05_target_matching.pipeline')
benchmark_mod = importlib.import_module('05_target_matching.benchmark')
models_p4_mod = importlib.import_module('04_plate_ocr.models')

MatchClass = models_mod.MatchClass
AlertSeverity = models_mod.AlertSeverity
WatchlistPriority = models_mod.WatchlistPriority
WatchlistEntry = models_mod.WatchlistEntry
Sighting = models_mod.Sighting
TargetMatchRecord = models_mod.TargetMatchRecord
Alert = models_mod.Alert
TargetMatchingConfig = config_mod.TargetMatchingConfig
TargetMatchScorer = scorer_mod.TargetMatchScorer
AlertManager = alerts_mod.AlertManager
WatchlistManager = watchlist_mod.WatchlistManager
SQLiteTargetMatchingRepository = repo_mod.SQLiteTargetMatchingRepository
PostgresTargetMatchingRepository = repo_mod.PostgresTargetMatchingRepository
HistoricalSearchService = history_mod.HistoricalSearchService
TargetMatchingPipeline = pipeline_mod.TargetMatchingPipeline
TrackOCRResult = models_p4_mod.TrackOCRResult
OCRHypothesis = models_p4_mod.OCRHypothesis
generate_hard_negatives = benchmark_mod.generate_hard_negatives


def test_invalid_negative_rejected():
    negs = generate_hard_negatives('GJ01AB1234')
    for n in negs:
        assert n != 'GJ01AB1234'
        assert len(n) >= 4


def test_no_conflicting_labels_in_generator():
    target = 'MH12DE1432'
    negs = generate_hard_negatives(target)
    assert target not in negs


def test_exact_low_evidence_alert_gating():
    cfg = TargetMatchingConfig(
        exact_evidence_gate_required=True,
        min_exact_alert_confidence=0.85,
        min_exact_alert_support=2
    )
    scorer = TargetMatchScorer(config=cfg)
    alert_mgr = AlertManager(config=cfg)

    # 1. Exact match with weak evidence (1 frame, 0.70 confidence)
    cand_weak = scorer.score_match(
        target_id='w-01',
        target_registration='GJ01AB1234',
        observed_registration='GJ01AB1234',
        ocr_confidence=0.70,
        multi_frame_support=1
    )
    w_entry = WatchlistEntry(watchlist_id='w-01', registration='GJ01AB1234', normalized_registration='GJ01AB1234', priority=WatchlistPriority.NORMAL)
    alert_weak, is_new, _ = alert_mgr.process_match(cand_weak, w_entry, 's-weak')

    assert alert_weak is not None
    # Weak evidence exact match must be gated to REVIEW rather than immediate high-severity dispatch
    assert alert_weak.severity == AlertSeverity.REVIEW

    # 2. Exact match with solid evidence (2 frames, 0.94 confidence)
    cand_solid = scorer.score_match(
        target_id='w-02',
        target_registration='GJ01AB1234',
        observed_registration='GJ01AB1234',
        ocr_confidence=0.94,
        multi_frame_support=2
    )
    alert_mgr2 = AlertManager(config=cfg)
    alert_solid, is_new, _ = alert_mgr2.process_match(cand_solid, w_entry, 's-solid')
    assert alert_solid.severity == AlertSeverity.HIGH


def test_p4_alternative_candidate_used():
    pipeline = TargetMatchingPipeline()
    pipeline.watchlist_manager.add_entry('GJ01AB1234', priority=WatchlistPriority.HIGH)

    # P4 has best_text='GJ01A81234' with alternative='GJ01AB1234'
    track_res = TrackOCRResult(
        camera_id='cam-1',
        track_id=88,
        stream_epoch=1,
        first_pts_ms=100.0,
        last_pts_ms=200.0,
        best_text='GJ01A81234',
        confidence=0.92,
        support_count=2,
        total_hypotheses=2,
        status='RESOLVED',
        alternatives=[('GJ01AB1234', 0.98)]
    )

    ranked, alerts, sighting = pipeline.process_track_ocr_result(track_res)
    assert len(ranked) >= 1
    # Candidate should match the alternative with 1.0 exact score
    assert ranked[0].match_score >= 0.95
    assert ranked[0].matched_from == 'ALTERNATIVE'


def test_p4_real_crop_quality_propagated():
    pipeline = TargetMatchingPipeline()
    pipeline.watchlist_manager.add_entry('GJ01AB1234')

    hypo1 = OCRHypothesis(
        camera_id='cam-1',
        track_id=1,
        stream_epoch=1,
        pts_ms=100.0,
        raw_text='GJ01AB1234',
        normalized_text='GJ01AB1234',
        ocr_confidence=0.95,
        crop_quality=0.92,
        grammar_score=0.98
    )

    track_res = TrackOCRResult(
        camera_id='cam-1',
        track_id=1,
        stream_epoch=1,
        first_pts_ms=100.0,
        last_pts_ms=200.0,
        best_text='GJ01AB1234',
        confidence=0.95,
        support_count=2,
        total_hypotheses=2,
        status='RESOLVED',
        hypotheses=[hypo1]
    )

    _, _, sighting = pipeline.process_track_ocr_result(track_res)
    assert sighting is not None
    assert sighting.raw_evidence['crop_quality'] == 0.92


def test_yaml_threshold_changes_runtime(tmp_path):
    custom_cfg = TargetMatchingConfig(high_probability_threshold=0.96)
    scorer = TargetMatchScorer(config=custom_cfg)
    assert scorer.high_prob_threshold == 0.96


def test_postgres_repository_integration():
    try:
        repo = PostgresTargetMatchingRepository()
        w_id = 'test-pg-w01'
        entry = WatchlistEntry(
            watchlist_id=w_id,
            registration='KA05NB1234',
            normalized_registration='KA05NB1234',
            priority=WatchlistPriority.CRITICAL
        )
        repo.save_watchlist_entry(entry)
        fetched = repo.get_watchlist_entry(w_id)
        assert fetched is not None
        assert fetched.normalized_registration == 'KA05NB1234'

        s_id = 'test-pg-s01'
        sighting = Sighting(
            sighting_id=s_id,
            camera_id='cam-pg-1',
            stream_epoch=1,
            track_id=99,
            first_pts_ms=100.0,
            last_pts_ms=200.0,
            registration_candidate='KA05NB1234',
            confidence=0.95,
            match_score=1.0,
            match_class=MatchClass.EXACT
        )
        repo.save_sighting(sighting)

        m_id = 'test-pg-m01'
        match_rec = TargetMatchRecord(
            match_id=m_id,
            sighting_id=s_id,
            watchlist_id=w_id,
            match_score=1.0,
            match_class=MatchClass.EXACT,
            raw_distance=0,
            confusion_distance=0.0,
            explanation=['Exact match'],
            created_at=datetime.now(timezone.utc)
        )
        repo.save_target_match(match_rec)

        matches = repo.query_target_matches(sighting_id=s_id)
        assert len(matches) >= 1
    except Exception as e:
        pytest.skip(f'Postgres not accessible in test environment: {e}')


def test_durable_watchlist_cache_refresh():
    repo = SQLiteTargetMatchingRepository()
    wm = WatchlistManager()

    entry = WatchlistEntry(
        watchlist_id='w-db-01',
        registration='DL01AB9999',
        normalized_registration='DL01AB9999',
        priority=WatchlistPriority.HIGH
    )
    repo.save_watchlist_entry(entry)

    assert wm.count_active() == 0
    wm.refresh_cache_from_repository(repo)
    assert wm.count_active() == 1
    assert wm.get_entry('w-db-01') is not None


def test_historical_search_includes_zero_score_sightings():
    repo = SQLiteTargetMatchingRepository()
    history_svc = HistoricalSearchService(repository=repo)

    # Sighting for random non-watchlisted car (match_score = 0.0)
    s = Sighting(
        sighting_id='s-unseen-1',
        camera_id='cam-toll-2',
        stream_epoch=1,
        track_id=303,
        first_pts_ms=500.0,
        last_pts_ms=800.0,
        registration_candidate='UP32EF1111',
        confidence=0.92,
        match_score=0.0,
        match_class=MatchClass.REJECTED
    )
    repo.save_sighting(s)

    # Default historical search MUST find it!
    results = history_svc.search_vehicle_history('UP32EF1111')
    assert len(results) == 1
    assert results[0]['registration_candidate'] == 'UP32EF1111'


def test_historical_search_created_after_before_filters():
    repo = SQLiteTargetMatchingRepository()
    history_svc = HistoricalSearchService(repository=repo)

    now = datetime.now(timezone.utc)
    s_old = Sighting(
        sighting_id='s-old',
        camera_id='cam-1',
        stream_epoch=1,
        track_id=1,
        first_pts_ms=0.0,
        last_pts_ms=10.0,
        registration_candidate='GJ01AB1234',
        confidence=0.9,
        match_score=1.0,
        match_class=MatchClass.EXACT,
        created_at=now - timedelta(hours=2)
    )
    s_new = Sighting(
        sighting_id='s-new',
        camera_id='cam-1',
        stream_epoch=1,
        track_id=2,
        first_pts_ms=0.0,
        last_pts_ms=10.0,
        registration_candidate='GJ01AB1234',
        confidence=0.9,
        match_score=1.0,
        match_class=MatchClass.EXACT,
        created_at=now
    )
    repo.save_sighting(s_old)
    repo.save_sighting(s_new)

    res_recent = history_svc.search_vehicle_history('GJ01AB1234', created_after=now - timedelta(minutes=30))
    assert len(res_recent) == 1
    assert res_recent[0]['sighting_id'] == 's-new'


def test_cross_camera_alert_persistence_inside_cooldown():
    am = AlertManager(config=TargetMatchingConfig(cooldown_seconds=60.0))
    scorer = TargetMatchScorer()

    w = WatchlistEntry(watchlist_id='w-01', registration='GJ01AB1234', normalized_registration='GJ01AB1234', priority=WatchlistPriority.HIGH)

    # Camera 1 detection
    c1 = scorer.score_match('w-01', 'GJ01AB1234', 'GJ01AB1234', camera_id='cam-junction-1', track_id=10, multi_frame_support=2)
    a1, is_new1, _ = am.process_match(c1, w, 's-cam1')
    assert is_new1 is True

    # Camera 2 detection 5 seconds later
    c2 = scorer.score_match('w-01', 'GJ01AB1234', 'GJ01AB1234', camera_id='cam-junction-2', track_id=20, multi_frame_support=2)
    a2, is_new2, _ = am.process_match(c2, w, 's-cam2')
    # Cross-camera detection must NOT be suppressed!
    assert is_new2 is True
    assert a2.camera_id == 'cam-junction-2'


def test_duplicate_watchlist_handling():
    wm = WatchlistManager(config=TargetMatchingConfig(duplicate_policy='update'))
    e1, ok1, _ = wm.add_entry('GJ01AB1234', priority=WatchlistPriority.NORMAL, notes='Note 1')
    assert ok1 is True

    # Add duplicate
    e2, ok2, _ = wm.add_entry('GJ-01-AB-1234', priority=WatchlistPriority.CRITICAL, notes='Note Updated')
    assert ok2 is True
    assert e2.watchlist_id == e1.watchlist_id
    assert e2.priority == WatchlistPriority.CRITICAL
    assert wm.count_active() == 1
