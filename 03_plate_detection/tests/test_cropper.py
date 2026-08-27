import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np
import importlib

cropper_mod = importlib.import_module('03_plate_detection.cropper')
crop_vehicle = cropper_mod.crop_vehicle
resize_for_plate_detection = cropper_mod.resize_for_plate_detection
map_crop_to_full_frame = cropper_mod.map_crop_to_full_frame


def test_crop_vehicle_with_padding():
    # Frame 1000x1000
    frame = np.zeros((1000, 1000, 3), dtype=np.uint8)

    # Box: x1=100, y1=200, x2=300, y2=400 (w=200, h=200)
    # Padding 10% -> px=20, py=20 -> cx1=80, cy1=180, cx2=320, cy2=420
    crop, cx1, cy1, cx2, cy2 = crop_vehicle(frame, 100, 200, 300, 400, padding=0.10)

    assert cx1 == 80
    assert cy1 == 180
    assert cx2 == 320
    assert cy2 == 420
    assert crop.shape == (240, 240, 3)


def test_resize_for_plate_detection():
    crop = np.zeros((200, 300, 3), dtype=np.uint8)
    resized, scale = resize_for_plate_detection(crop, target_width=900)

    assert scale == 3.0
    assert resized.shape[1] == 900
    assert resized.shape[0] == 600


def test_map_crop_to_full_frame():
    # Suppose crop offset is (100, 200), scale is 2.0
    # Inside resized crop, plate is at (50, 60) to (150, 100)
    # Unscaled local: (25, 30) to (75, 50)
    # Full frame: x1 = 100 + 25 = 125, y1 = 200 + 30 = 230
    #             x2 = 100 + 75 = 175, y2 = 200 + 50 = 250
    fx1, fy1, fx2, fy2, pw, ph = map_crop_to_full_frame(
        local_x1=50.0,
        local_y1=60.0,
        local_x2=150.0,
        local_y2=100.0,
        crop_offset_x=100,
        crop_offset_y=200,
        scale_factor=2.0,
    )

    assert fx1 == 125.0
    assert fy1 == 230.0
    assert fx2 == 175.0
    assert fy2 == 250.0
    assert pw == 50.0
    assert ph == 20.0
