import time
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
import importlib

repo_mod = importlib.import_module('05_target_matching.repository')
models_mod = importlib.import_module('05_target_matching.models')

PostgresTargetMatchingRepository = repo_mod.PostgresTargetMatchingRepository
WatchlistEntry = models_mod.WatchlistEntry
WatchlistPriority = models_mod.WatchlistPriority
Sighting = models_mod.Sighting
MatchClass = models_mod.MatchClass
TargetMatchRecord = models_mod.TargetMatchRecord
Alert = models_mod.Alert
AlertSeverity = models_mod.AlertSeverity

REPORTS_P5 = Path('reports/system_optimization/p5_matching')
REPORTS_P5.mkdir(parents=True, exist_ok=True)


def benchmark_postgres_persistence():
    print('============================================================')
    print('BENCHMARKING POSTGRESQL / POSTGIS PERSISTENCE & QUERIES')
    print('============================================================')

    try:
        repo = PostgresTargetMatchingRepository()
    except Exception as e:
        print(f'PostgreSQL unavailable: {e}')
        return

    # 1. Benchmark Watchlist Ingestion
    w_entries = [
        WatchlistEntry(
            watchlist_id=f'w-bench-{i}',
            registration=f'GJ01AB{i:04d}',
            normalized_registration=f'GJ01AB{i:04d}',
            priority=WatchlistPriority.HIGH
        )
        for i in range(100)
    ]
    t0 = time.perf_counter()
    for w in w_entries:
        repo.save_watchlist_entry(w)
    t_wl = (time.perf_counter() - t0) * 1000.0 / 100

    # 2. Benchmark Sighting Ingestion
    sightings = [
        Sighting(
            sighting_id=f's-bench-{i}',
            camera_id='cam-junction-bench',
            stream_epoch=1,
            track_id=100 + i,
            first_pts_ms=float(i * 100),
            last_pts_ms=float(i * 100 + 40),
            registration_candidate=f'GJ01AB{i:04d}',
            confidence=0.94,
            match_score=0.96,
            match_class=MatchClass.HIGH_PROBABILITY
        )
        for i in range(100)
    ]
    t0 = time.perf_counter()
    for s in sightings:
        repo.save_sighting(s)
    t_sight = (time.perf_counter() - t0) * 1000.0 / 100

    # 3. Benchmark Target Match Ingestion
    matches = [
        TargetMatchRecord(
            match_id=f'm-bench-{i}',
            sighting_id=f's-bench-{i}',
            watchlist_id=f'w-bench-{i}',
            match_score=0.96,
            match_class=MatchClass.HIGH_PROBABILITY,
            raw_distance=0,
            confusion_distance=0.0,
            explanation=['Benchmark match record'],
            created_at=datetime.now(timezone.utc)
        )
        for i in range(100)
    ]
    t0 = time.perf_counter()
    for m in matches:
        repo.save_target_match(m)
    t_match = (time.perf_counter() - t0) * 1000.0 / 100

    # 4. Benchmark Query Performance
    t0 = time.perf_counter()
    q_sight = repo.query_sightings(registration_pattern='GJ01AB*', limit=50)
    t_q_sight = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    q_matches = repo.query_target_matches(min_score=0.90, limit=50)
    t_q_match = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    active_wl = repo.list_active_watchlist_entries()
    t_q_wl = (time.perf_counter() - t0) * 1000.0

    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
        'database': 'PostgreSQL 17.5 + PostGIS',
        'per_record_insert_latency_ms': {
            'watchlist_entry_insert_ms': round(t_wl, 2),
            'sighting_insert_ms': round(t_sight, 2),
            'target_match_insert_ms': round(t_match, 2)
        },
        'query_latency_ms': {
            'historical_sightings_wildcard_query_ms': round(t_q_sight, 2),
            'target_matches_score_query_ms': round(t_q_match, 2),
            'active_watchlist_full_sync_ms': round(t_q_wl, 2)
        },
        'results_returned': {
            'sightings_count': len(q_sight),
            'matches_count': len(q_matches),
            'active_watchlist_count': len(active_wl)
        }
    }

    print('\n------------------------------------------------------------')
    print('POSTGRESQL BENCHMARK RESULTS:')
    print(f'  Watchlist Insert Latency  : {t_wl:.2f} ms/record')
    print(f'  Sighting Insert Latency   : {t_sight:.2f} ms/record')
    print(f'  Target Match Latency      : {t_match:.2f} ms/record')
    print(f'  Historical Query (Wildcard): {t_q_sight:.2f} ms')
    print(f'  Target Matches Query      : {t_q_match:.2f} ms')
    print(f'  Watchlist Sync (Full DB)  : {t_q_wl:.2f} ms')
    print('------------------------------------------------------------')

    out_p = REPORTS_P5 / 'postgres_benchmark.json'
    with open(out_p, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print(f'Saved database benchmark to {out_p}')


if __name__ == '__main__':
    benchmark_postgres_persistence()
