import importlib
from datetime import datetime, timezone

repo_mod = importlib.import_module('05_target_matching.repository')
history_mod = importlib.import_module('05_target_matching.history')
models_mod = importlib.import_module('05_target_matching.models')

TargetMatchingRepository = repo_mod.TargetMatchingRepository
HistoricalSearchService = history_mod.HistoricalSearchService
Sighting = models_mod.Sighting
MatchClass = models_mod.MatchClass


def test_historical_sighting_persistence_and_search():
    repo = TargetMatchingRepository(':memory:')
    history_svc = HistoricalSearchService(repository=repo)

    s1 = Sighting(
        sighting_id='s-001',
        camera_id='cam-junction-4',
        stream_epoch=1,
        track_id=101,
        first_pts_ms=1000.0,
        last_pts_ms=2500.0,
        registration_candidate='GJ01AB1234',
        confidence=0.95,
        match_score=0.96,
        match_class=MatchClass.EXACT
    )
    s2 = Sighting(
        sighting_id='s-002',
        camera_id='cam-expressway-1',
        stream_epoch=1,
        track_id=102,
        first_pts_ms=5000.0,
        last_pts_ms=7000.0,
        registration_candidate='MH12DE1432',
        confidence=0.91,
        match_score=0.92,
        match_class=MatchClass.EXACT
    )

    repo.save_sighting(s1)
    repo.save_sighting(s2)

    # Exact search
    results_exact = history_svc.search_vehicle_history('GJ01AB1234')
    assert len(results_exact) == 1
    assert results_exact[0]['registration_candidate'] == 'GJ01AB1234'

    # Wildcard search (GJ01*)
    results_wild = history_svc.search_vehicle_history('GJ01*')
    assert len(results_wild) == 1

    # Camera filtered search
    results_cam = history_svc.search_vehicle_history('*', camera_id='cam-expressway-1')
    assert len(results_cam) == 1
    assert results_cam[0]['camera_id'] == 'cam-expressway-1'


def test_historical_rescoring():
    repo = TargetMatchingRepository(':memory:')
    history_svc = HistoricalSearchService(repository=repo)

    sighting_data = {
        'sighting_id': 's-001',
        'camera_id': 'cam-1',
        'registration_candidate': 'GJ01A81234',
        'confidence': 0.94,
        'stream_epoch': 1,
        'track_id': 50,
        'first_pts_ms': 100.0,
        'last_pts_ms': 500.0
    }

    # Rescore against true target
    rescored = history_svc.rescore_sighting(sighting_data, target_registration='GJ01AB1234')
    assert rescored.match_score >= 0.80
    assert rescored.target_registration == 'GJ01AB1234'
