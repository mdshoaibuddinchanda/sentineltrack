import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
MODULE_DIR = Path(__file__).resolve().parent.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import importlib
models_mod = importlib.import_module("02_tracking.models")
manager_mod = importlib.import_module("02_tracking.track_manager")

VehicleTrack = models_mod.VehicleTrack
TrackManager = manager_mod.TrackManager
TrackState = manager_mod.TrackState



def test_vehicle_track_properties():
    vt = VehicleTrack(
        camera_id='cam_01',
        track_id=17,
        stream_epoch=0,
        first_pts_ms=100.0,
        last_pts_ms=250.0,
        class_id=2,
        class_name='car',
        confidence=0.88,
        x1=100.0,
        y1=200.0,
        x2=300.0,
        y2=400.0,
        age_frames=3,
    )

    assert vt.camera_id == 'cam_01'
    assert vt.track_id == 17
    assert vt.stream_epoch == 0
    assert vt.first_pts_ms == 100.0
    assert vt.last_pts_ms == 250.0
    assert vt.class_name == 'car'
    assert vt.confidence == 0.88
    assert vt.center == (200.0, 300.0)


def test_track_manager_lifecycle():
    manager = TrackManager(max_trail_len=5)

    vt1 = VehicleTrack(
        camera_id='cam_1',
        track_id=12,
        stream_epoch=0,
        first_pts_ms=0.0,
        last_pts_ms=0.0,
        class_id=2,
        class_name='car',
        confidence=0.9,
        x1=10.0, y1=10.0, x2=50.0, y2=50.0,
    )

    # Frame 1: Initial insertion
    t1 = manager.update(vt1)
    assert t1.age_frames == 1
    assert len(t1.trail) == 1
    assert t1.trail[0] == (30.0, 30.0)

    # Frame 2: Update same track
    vt1_next = VehicleTrack(
        camera_id='cam_1',
        track_id=12,
        stream_epoch=0,
        first_pts_ms=0.0,
        last_pts_ms=150.0,
        class_id=2,
        class_name='car',
        confidence=0.92,
        x1=15.0, y1=15.0, x2=55.0, y2=55.0,
    )
    t2 = manager.update(vt1_next)
    assert t2.age_frames == 2
    assert len(t2.trail) == 2
    assert t2.trail[1] == (35.0, 35.0)

    # Check active tracks
    active = manager.get_active_tracks()
    assert len(active) == 1
    assert active[0].track_id == 12

    # Reset camera
    manager.reset_camera('cam_1')
    assert len(manager.get_active_tracks()) == 0
