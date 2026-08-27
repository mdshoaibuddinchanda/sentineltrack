import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
MODULE_DIR = Path(__file__).resolve().parent.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from models import VehicleDetection


def test_vehicle_detection_attributes():
    det = VehicleDetection(
        camera_id='cam_01',
        pts_ms=45230.5,
        stream_epoch=1,
        class_id=2,
        class_name='car',
        confidence=0.92,
        x1=100.0,
        y1=150.0,
        x2=400.0,
        y2=350.0,
    )

    assert det.camera_id == 'cam_01'
    assert det.pts_ms == 45230.5
    assert det.stream_epoch == 1
    assert det.class_id == 2
    assert det.class_name == 'car'
    assert det.confidence == 0.92
    assert det.x1 == 100.0
    assert det.y1 == 150.0
    assert det.x2 == 400.0
    assert det.y2 == 350.0
