import importlib
from datetime import datetime, timezone

pipeline_mod = importlib.import_module('05_target_matching.pipeline')
models_p4_mod = importlib.import_module('04_plate_ocr.models')
models_p5_mod = importlib.import_module('05_target_matching.models')

TargetMatchingPipeline = pipeline_mod.TargetMatchingPipeline
TrackOCRResult = models_p4_mod.TrackOCRResult
MatchClass = models_p5_mod.MatchClass
WatchlistPriority = models_p5_mod.WatchlistPriority


def test_pipeline_with_matching_watchlist_target():
    pipeline = TargetMatchingPipeline()

    # Add active target to watchlist
    entry, ok, _ = pipeline.watchlist_manager.add_entry(
        registration='GJ01AB1234',
        priority=WatchlistPriority.HIGH
    )
    assert ok is True

    # P4 emits OCR result for track 77
    track_res = TrackOCRResult(
        camera_id='cam-toll-plaza-1',
        track_id=77,
        stream_epoch=1,
        first_pts_ms=100.0,
        last_pts_ms=450.0,
        best_text='GJ01A81234',
        confidence=0.93,
        support_count=3,
        total_hypotheses=3,
        status='RESOLVED'
    )

    ranked_cands, alerts, sighting = pipeline.process_track_ocr_result(track_res)

    assert sighting is not None
    assert len(ranked_cands) >= 1
    assert ranked_cands[0].match_score >= 0.85
    assert ranked_cands[0].match_class == MatchClass.HIGH_PROBABILITY
    assert len(alerts) == 1
    assert alerts[0].registration == 'GJ01A81234'


def test_pipeline_ignores_empty_ocr():
    pipeline = TargetMatchingPipeline()
    track_res = TrackOCRResult(
        camera_id='cam-1',
        track_id=1,
        stream_epoch=1,
        first_pts_ms=0.0,
        last_pts_ms=0.0,
        best_text=None,
        confidence=0.0,
        support_count=0,
        total_hypotheses=0,
        status='INSUFFICIENT_EVIDENCE'
    )

    ranked, alerts, sighting = pipeline.process_track_ocr_result(track_res)
    assert ranked == []
    assert alerts == []
    assert sighting is None


def test_pipeline_rejects_signage_and_deduplicates_track_sightings():
    repository_mod = importlib.import_module('05_target_matching.repository')
    repository = repository_mod.SQLiteTargetMatchingRepository()
    pipeline = TargetMatchingPipeline(repository=repository)

    signage = TrackOCRResult(
        camera_id='cam-1', track_id=10, stream_epoch=1,
        first_pts_ms=0.0, last_pts_ms=500.0,
        best_text='GSRTC', confidence=0.95, support_count=3,
        total_hypotheses=3, status='RESOLVED'
    )
    assert pipeline.process_track_ocr_result(signage) == ([], [], None)

    plate = TrackOCRResult(
        camera_id='cam-1', track_id=11, stream_epoch=1,
        first_pts_ms=0.0, last_pts_ms=500.0,
        best_text='GJ01AB1234', confidence=0.95, support_count=3,
        total_hypotheses=3, status='RESOLVED'
    )
    first = pipeline.process_track_ocr_result(plate)[2]
    plate.last_pts_ms = 900.0
    second = pipeline.process_track_ocr_result(plate)[2]

    assert first is not None and second is not None
    assert first.sighting_id == second.sighting_id
    rows = repository.query_sightings(limit=10)
    assert len(rows) == 1

    restarted_pipeline = TargetMatchingPipeline(repository=repository)
    restarted = restarted_pipeline.process_track_ocr_result(plate)[2]
    assert restarted is not None
    assert restarted.sighting_id != first.sighting_id
    assert len(repository.query_sightings(limit=10)) == 2
