import importlib
import numpy as np

prep_mod = importlib.import_module('04_plate_ocr.preprocess')
rect_mod = importlib.import_module('04_plate_ocr.rectification')

preprocess_crop = prep_mod.preprocess_crop
resize_aspect_ratio = prep_mod.resize_aspect_ratio
rectify_plate_perspective = rect_mod.rectify_plate_perspective


def test_resize_aspect_ratio():
    crop = np.full((100, 300, 3), 200, dtype=np.uint8)
    resized = resize_aspect_ratio(crop, target_height=64, max_width=320)
    assert resized.shape[0] == 64
    assert resized.shape[1] == 192


def test_preprocessing_variants():
    crop = np.random.randint(0, 255, (80, 240, 3), dtype=np.uint8)

    for var in ['raw', 'gray', 'clahe', 'sharpen', 'rectify']:
        out, meta = preprocess_crop(crop, variant=var, target_height=64)
        assert out is not None
        assert out.shape[0] == 64
        assert out.size > 0
        assert meta['variant'] == var


def test_rectification_graceful_fallback():
    noise = np.random.randint(0, 255, (50, 150, 3), dtype=np.uint8)
    rect, applied, conf = rectify_plate_perspective(noise)
    assert rect is not None
    assert rect.shape == noise.shape
