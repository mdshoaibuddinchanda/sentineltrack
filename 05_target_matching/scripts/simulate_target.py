import importlib

pipeline_mod = importlib.import_module('05_target_matching.pipeline')
models_p5_mod = importlib.import_module('05_target_matching.models')
models_p4_mod = importlib.import_module('04_plate_ocr.models')

TargetMatchingPipeline = pipeline_mod.TargetMatchingPipeline
WatchlistPriority = models_p5_mod.WatchlistPriority
TrackOCRResult = models_p4_mod.TrackOCRResult
OCRHypothesis = models_p4_mod.OCRHypothesis


def run_target_simulation():
    print('============================================================')
    print('SENTINELTRACK PRIORITY 5 END-TO-END SIMULATION')
    print('============================================================')

    pipeline = TargetMatchingPipeline()

    # 1. Register Ephemeral Test Watchlist Target
    target_plate = 'GJ01AB1234'
    entry, ok, _ = pipeline.watchlist_manager.add_entry(
        registration=target_plate,
        priority=WatchlistPriority.CRITICAL,
        notes='Simulation Target: Redacted Test Target'
    )
    print(f'[Watchlist] Registered Target: {entry.registration} (Priority: {entry.priority.value})')

    # 2. Simulate 3 Video Frames for Vehicle Track #101 on Camera 'junction-north-01'
    print('\n[Stream] Simulating Incoming Multi-Frame OCR Observations...')

    frames = [
        # Frame 1: Slightly noisy OCR (B -> 8)
        TrackOCRResult(
            camera_id='cam-junction-north-01',
            track_id=101,
            stream_epoch=1,
            first_pts_ms=1000.0,
            last_pts_ms=1040.0,
            best_text='GJ01A81234',
            confidence=0.88,
            support_count=1,
            total_hypotheses=1,
            status='LOW_CONFIDENCE'
        ),
        # Frame 2: Corroborated with clearer view
        TrackOCRResult(
            camera_id='cam-junction-north-01',
            track_id=101,
            stream_epoch=1,
            first_pts_ms=1000.0,
            last_pts_ms=1080.0,
            best_text='GJ01AB1234',
            confidence=0.94,
            support_count=2,
            total_hypotheses=2,
            status='RESOLVED'
        ),
        # Frame 3: Stable unanimous consensus
        TrackOCRResult(
            camera_id='cam-junction-north-01',
            track_id=101,
            stream_epoch=1,
            first_pts_ms=1000.0,
            last_pts_ms=1120.0,
            best_text='GJ01AB1234',
            confidence=0.96,
            support_count=3,
            total_hypotheses=3,
            status='RESOLVED'
        )
    ]

    for idx, f in enumerate(frames, 1):
        print(f'\n--- Processing Frame {idx} (PTS: {f.last_pts_ms:.0f}ms, OCR: \"{f.best_text}\", Conf: {f.confidence:.2f}, Supp: {f.support_count}) ---')
        candidates, alerts, sighting = pipeline.process_track_ocr_result(f)

        if candidates:
            top = candidates[0]
            print(f'  Match Score: {top.match_score:.4f} | Class: {top.match_class.value}')
            for r in top.reasons:
                print(f'    • {r}')

        if alerts:
            print(f'  [ALERT GENERATED] Total Alerts: {len(alerts)}')
            for a in alerts:
                print(f'    • ID: {a.alert_id[:8]} | Severity: {a.severity.value} | Track: {a.track_id} | Score: {a.match_score:.2f}')
        else:
            print('  [No Alert] Sub-threshold observation')

    # 3. Verify Idempotency: Sighting count vs Alert count
    all_alerts = pipeline.alert_manager.get_alerts()
    all_sightings = pipeline.repository.query_sightings('*')
    print('\n============================================================')
    print('SIMULATION INTEGRITY AUDIT:')
    print(f'  Total Sightings Persisted: {len(all_sightings)} (Preserved multi-frame track progression)')
    print(f'  Total Alerts Dispatched:   {len(all_alerts)} (Idempotently capped to 1 alert per track)')
    assert len(all_alerts) == 1, 'Failed idempotency assertion: Multiple alerts generated for single track!'
    print('  IDEMPOTENCY ASSERTION PASSED!')
    print('============================================================')


if __name__ == '__main__':
    run_target_simulation()
