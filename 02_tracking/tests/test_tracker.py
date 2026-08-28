import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
MODULE_DIR = Path(__file__).resolve().parent.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import numpy as np
import importlib

models_mod = importlib.import_module("00_foundation.streams.models")
FramePacket = models_mod.FramePacket

det_models = importlib.import_module("01_vehicle_detection.models")
VehicleDetection = det_models.VehicleDetection

tracker_mod = importlib.import_module("02_tracking.tracker")
pipeline_mod = importlib.import_module("02_tracking.pipeline")
track_models = importlib.import_module("02_tracking.models")

CameraByteTracker = tracker_mod.CameraByteTracker
CameraTrackerRegistry = tracker_mod.CameraTrackerRegistry
DetectionBoxesAdapter = tracker_mod.DetectionBoxesAdapter
VehicleTrackingPipeline = pipeline_mod.VehicleTrackingPipeline
VehicleTrack = track_models.VehicleTrack



def test_detection_boxes_adapter():
    dets = [
        VehicleDetection('c1', 100.0, 0, 2, 'car', 0.95, 10.0, 20.0, 110.0, 120.0),
        VehicleDetection('c1', 100.0, 0, 7, 'truck', 0.85, 200.0, 200.0, 400.0, 400.0),
    ]

    adapter = DetectionBoxesAdapter(dets)
    assert len(adapter) == 2
    assert adapter.xyxy.shape == (2, 4)
    assert adapter.xywh.shape == (2, 4)

    # Check center and size calculations
    # Box 1: x1=10, y1=20, x2=110, y2=120 -> w=100, h=100, cx=60, cy=70
    assert adapter.xywh[0, 0].item() == 60.0
    assert adapter.xywh[0, 1].item() == 70.0
    assert adapter.xywh[0, 2].item() == 100.0
    assert adapter.xywh[0, 3].item() == 100.0


def test_camera_tracker_independent_state():
    registry = CameraTrackerRegistry()

    tracker1 = registry.get_tracker('cam_01')
    tracker2 = registry.get_tracker('cam_02')

    assert tracker1 is not tracker2
    assert tracker1.camera_id == 'cam_01'
    assert tracker2.camera_id == 'cam_02'


def test_tracker_epoch_reset():
    tracker = CameraByteTracker(camera_id='cam_test')

    packet1 = FramePacket('cam_test', 1000.0, np.zeros((100, 100, 3), dtype=np.uint8), stream_epoch=0)
    dets1 = [VehicleDetection('cam_test', 1000.0, 0, 2, 'car', 0.9, 50, 50, 100, 100)]
    t1 = tracker.update(packet1, dets1)
    assert len(t1) == 1
    assert tracker.last_epoch == 0

    # Frame with new epoch
    packet2 = FramePacket('cam_test', 50.0, np.zeros((100, 100, 3), dtype=np.uint8), stream_epoch=1)
    dets2 = [VehicleDetection('cam_test', 50.0, 1, 2, 'car', 0.9, 50, 50, 100, 100)]
    t2 = tracker.update(packet2, dets2)
    assert tracker.last_epoch == 1


def test_tracker_pts_gap_reset():
    tracker = CameraByteTracker(camera_id='cam_gap', max_track_gap_ms=1500.0)

    packet1 = FramePacket('cam_gap', 1000.0, np.zeros((100, 100, 3), dtype=np.uint8), 0)
    dets1 = [VehicleDetection('cam_gap', 1000.0, 0, 2, 'car', 0.9, 100, 100, 200, 200)]
    tracker.update(packet1, dets1)
    assert tracker.last_pts_ms == 1000.0

    # Gap of 2500ms > max_track_gap_ms (1500ms)
    packet2 = FramePacket('cam_gap', 3500.0, np.zeros((100, 100, 3), dtype=np.uint8), 0)
    dets2 = [VehicleDetection('cam_gap', 3500.0, 0, 2, 'car', 0.9, 105, 105, 205, 205)]
    tracker.update(packet2, dets2)
    assert tracker.last_pts_ms == 3500.0


def test_tracking_pipeline_end_to_end():
    mock_detector = MagicMock()
    mock_detector.detect.return_value = [
        VehicleDetection('cam_p', 100.0, 0, 2, 'car', 0.91, 50, 50, 150, 150)
    ]

    pipeline = VehicleTrackingPipeline(detector=mock_detector)
    packet = FramePacket('cam_p', 100.0, np.zeros((480, 640, 3), dtype=np.uint8), 0)

    tracks = pipeline.process(packet)
    assert len(tracks) == 1
    assert tracks[0].camera_id == 'cam_p'
    assert tracks[0].class_name == 'car'
    assert tracks[0].age_frames == 1
    assert len(tracks[0].trail) == 1


def test_tracker_active_long_lived_track_not_pruned():
    tracker = CameraByteTracker(camera_id='cam_soak')

    # Seed 1050 old inactive tracks
    for i in range(1050):
        tracker.first_seen_pts[i] = 100.0
        tracker.last_seen_pts[i] = 500.0

    # Active track started 120 seconds ago (pts 0ms), currently active at 120,000ms
    active_tid = 9999
    tracker.first_seen_pts[active_tid] = 0.0
    tracker.last_seen_pts[active_tid] = 119960.0

    # Update tracker at pts_ms = 120,000ms
    packet = FramePacket('cam_soak', 120000.0, np.zeros((100, 100, 3), dtype=np.uint8), 0)
    dets = [VehicleDetection('cam_soak', 120000.0, 0, 2, 'car', 0.95, 50, 50, 100, 100)]
    
    # Update tracker
    tracks = tracker.update(packet, dets)

    # Inactive tracks should have been pruned (< 100 remaining)
    assert len(tracker.last_seen_pts) <= 10
    assert len(tracker.first_seen_pts) <= 10

    # The active track started at 0.0 should still be intact in first_seen_pts and last_seen_pts
    assert active_tid in tracker.first_seen_pts
    assert tracker.first_seen_pts[active_tid] == 0.0
    assert tracker.last_seen_pts[active_tid] == 119960.0
