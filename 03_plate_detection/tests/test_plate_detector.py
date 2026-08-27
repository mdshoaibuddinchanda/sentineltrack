import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np
import importlib

models_mod = importlib.import_module('00_foundation.streams.models')
FramePacket = models_mod.FramePacket

track_models = importlib.import_module('02_tracking.models')
VehicleTrack = track_models.VehicleTrack

pipe_mod = importlib.import_module('03_plate_detection.pipeline')
PlateDetectionPipeline = pipe_mod.PlateDetectionPipeline

quality_mod = importlib.import_module('03_plate_detection.quality')
blur_score = quality_mod.blur_score
brightness_score = quality_mod.brightness_score
compute_plate_quality = quality_mod.compute_plate_quality


def test_quality_scorer():
    sharp_img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    blur = blur_score(sharp_img)
    assert blur >= 0.0

    bright = brightness_score(sharp_img)
    assert 0.0 <= bright <= 255.0

    blur, bright, qscore = compute_plate_quality(sharp_img, width=80, height=25, confidence=0.90)
    assert 0.0 <= qscore <= 1.0


def test_plate_detection_pipeline_flow():
    mock_p_detector = MagicMock()
    # Mock finding a plate at (100, 50, 200, 80) inside the resized vehicle crop
    mock_p_detector.detect.return_value = [
        {'confidence': 0.94, 'x1': 100.0, 'y1': 50.0, 'x2': 200.0, 'y2': 80.0}
    ]

    pipeline = PlateDetectionPipeline(plate_detector=mock_p_detector, target_crop_width=500)

    # Frame 1080x1920
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    packet = FramePacket('cam_1', 100.0, frame, stream_epoch=0)

    track = VehicleTrack(
        camera_id='cam_1',
        track_id=7,
        stream_epoch=0,
        first_pts_ms=0.0,
        last_pts_ms=100.0,
        class_id=2,
        class_name='car',
        confidence=0.88,
        x1=500.0, y1=400.0, x2=800.0, y2=700.0,
    )

    observations = pipeline.process(packet, [track])

    assert len(observations) == 1
    obs = observations[0]
    assert obs.camera_id == 'cam_1'
    assert obs.track_id == 7
    assert obs.confidence == 0.94
    assert obs.vehicle_class == 'car'
    # Check that plate was re-projected near the vehicle box coordinates
    assert obs.x1 >= 450.0
    assert obs.y1 >= 350.0
