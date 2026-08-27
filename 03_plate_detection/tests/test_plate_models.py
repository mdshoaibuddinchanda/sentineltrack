import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import importlib
models_mod = importlib.import_module('03_plate_detection.models')
quality_mod = importlib.import_module('03_plate_detection.quality')

PlateObservation = models_mod.PlateObservation
TrackPlateAccumulator = quality_mod.TrackPlateAccumulator


def test_plate_observation_properties():
    obs = PlateObservation(
        camera_id='cam_1',
        track_id=42,
        stream_epoch=0,
        pts_ms=500.0,
        confidence=0.92,
        x1=100.0,
        y1=200.0,
        x2=190.0,
        y2=230.0,
        width=90.0,
        height=30.0,
        vehicle_class='car',
        vehicle_confidence=0.88,
        plate_area=2700.0,
        quality_score=0.85,
    )

    assert obs.camera_id == 'cam_1'
    assert obs.track_id == 42
    assert obs.width == 90.0
    assert obs.height == 30.0
    assert obs.center == (145.0, 215.0)
    assert obs.aspect_ratio == 3.0


def test_track_plate_accumulator_top_k():
    accum = TrackPlateAccumulator(max_candidates_per_track=3)

    for i, q in enumerate([0.5, 0.9, 0.7, 0.95, 0.4]):
        obs = PlateObservation(
            camera_id='c1',
            track_id=1,
            stream_epoch=0,
            pts_ms=float(i * 100),
            confidence=0.8,
            x1=10, y1=10, x2=50, y2=20,
            width=40, height=10,
            vehicle_class='car',
            vehicle_confidence=0.9,
            quality_score=q,
        )
        accum.add(obs)

    best = accum.get_best_candidates('c1', 0, 1)
    assert len(best) == 3
    # Sorted descending: 0.95, 0.9, 0.7
    assert best[0]['quality'] == 0.95
    assert best[1]['quality'] == 0.9
    assert best[2]['quality'] == 0.7
