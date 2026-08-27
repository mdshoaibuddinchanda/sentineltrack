import importlib
from datetime import datetime, timezone

mod = importlib.import_module('05_target_matching.models')
MatchClass = mod.MatchClass
WatchlistPriority = mod.WatchlistPriority
AlertSeverity = mod.AlertSeverity
TargetRegistration = mod.TargetRegistration
MatchCandidate = mod.MatchCandidate
Sighting = mod.Sighting
WatchlistEntry = mod.WatchlistEntry
Alert = mod.Alert


def test_target_registration_model():
    target = TargetRegistration(
        target_id='tgt-001',
        registration='GJ-01-AB-1234',
        normalized_registration='GJ01AB1234',
        priority=WatchlistPriority.HIGH
    )
    assert target.target_id == 'tgt-001'
    assert target.normalized_registration == 'GJ01AB1234'
    assert target.priority == WatchlistPriority.HIGH
    assert target.active is True


def test_watchlist_entry_indexing_post_init():
    entry = WatchlistEntry(
        watchlist_id='w-001',
        registration='MH 12 DE 1432',
        normalized_registration='MH12DE1432',
        priority=WatchlistPriority.CRITICAL
    )
    assert entry.state_prefix == 'MH'
    assert entry.rto_code == 'MH12'
    assert entry.plate_length == 10


def test_match_candidate_model():
    cand = MatchCandidate(
        target_id='tgt-001',
        target_registration='GJ01AB1234',
        observed_registration='GJ01A81234',
        camera_id='cam-1',
        stream_epoch=1,
        track_id=12,
        first_pts_ms=100.0,
        last_pts_ms=500.0,
        raw_distance=1,
        normalized_distance=0.1,
        confusion_distance=0.2,
        ocr_confidence=0.92,
        crop_quality=0.85,
        grammar_score=0.95,
        multi_frame_support=3,
        exact_match=False,
        match_score=0.91,
        match_class=MatchClass.HIGH_PROBABILITY,
        reasons=['Plausible B/8 confusion']
    )
    assert cand.match_class == MatchClass.HIGH_PROBABILITY
    assert len(cand.reasons) == 1
    assert cand.reid_score is None  # Reserved for P6
