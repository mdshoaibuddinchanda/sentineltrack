import pytest
import cv2
import importlib
import numpy as np

rec_mod = importlib.import_module('04_plate_ocr.recognizers')
paddle_mod = importlib.import_module('04_plate_ocr.recognizers.paddle_rec')
mock_mod = importlib.import_module('04_plate_ocr.recognizers.mock_rec')
norm_mod = importlib.import_module('04_plate_ocr.normalization')
setup_mod = importlib.import_module('04_plate_ocr.scripts.setup_ocr_models')

get_recognizer = rec_mod.get_recognizer
is_two_line_plate = paddle_mod.is_two_line_plate
split_two_line_plate = paddle_mod.split_two_line_plate
MockPlateRecognizer = mock_mod.MockPlateRecognizer
normalize_plate_text = norm_mod.normalize_plate_text
verify_file_integrity = setup_mod.verify_file_integrity
compute_file_sha256 = setup_mod.compute_file_sha256


def test_mock_recognizer():
    mock = MockPlateRecognizer(default_text='MH12DE1432', default_conf=0.96)
    dummy = np.full((48, 192, 3), 255, dtype=np.uint8)
    text, conf, chars = mock.recognize(dummy)
    assert text == 'MH12DE1432'
    assert conf == 0.96
    assert mock.calls == 1


def test_recognizer_factory():
    rec_mock = get_recognizer('mock_rec')
    assert isinstance(rec_mock, MockPlateRecognizer)
    rec_mobile = get_recognizer('ppocr_mobile', device='cpu')
    assert rec_mobile.model_name == 'en_PP-OCRv5_mobile_rec_onnx'


def test_single_line_batch_parity():
    rec = get_recognizer('ppocr_mobile', device='cpu')
    single_crop = np.full((48, 192, 3), 255, dtype=np.uint8)
    cv2.putText(single_crop, 'MH12DE1432', (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)

    res_single = rec.recognize(single_crop)
    res_batch = rec.recognize_batch([single_crop])[0]

    assert normalize_plate_text(res_single[0]) == normalize_plate_text(res_batch[0])


def test_two_line_batch_parity():
    rec = get_recognizer('ppocr_mobile', device='cpu')
    two_line_crop = np.full((96, 160, 3), 255, dtype=np.uint8)
    cv2.putText(two_line_crop, 'MH12', (15, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(two_line_crop, 'AB1234', (15, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    assert is_two_line_plate(two_line_crop) is True

    res_single = rec.recognize(two_line_crop)
    res_batch = rec.recognize_batch([two_line_crop])[0]

    assert normalize_plate_text(res_single[0]) == normalize_plate_text(res_batch[0])


def test_mixed_batch_ordering_preservation():
    rec = get_recognizer('ppocr_mobile', device='cpu')

    crop_single_1 = np.full((48, 192, 3), 255, dtype=np.uint8)
    cv2.putText(crop_single_1, 'MH12DE1432', (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)

    crop_two_line = np.full((96, 160, 3), 255, dtype=np.uint8)
    cv2.putText(crop_two_line, 'MH12', (15, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(crop_two_line, 'AB1234', (15, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    crop_single_2 = np.full((48, 192, 3), 255, dtype=np.uint8)
    cv2.putText(crop_single_2, 'DL01AB9999', (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)

    mixed_batch = [crop_single_1, crop_two_line, crop_single_2]
    batch_results = rec.recognize_batch(mixed_batch)

    # Standalone executions
    s0 = rec.recognize(crop_single_1)
    s1 = rec.recognize(crop_two_line)
    s2 = rec.recognize(crop_single_2)

    # 1. Exact batch length preservation
    assert len(batch_results) == 3

    # 2. Strict index-by-index parity assertions
    assert normalize_plate_text(batch_results[0][0]) == normalize_plate_text(s0[0])
    assert normalize_plate_text(batch_results[1][0]) == normalize_plate_text(s1[0])
    assert normalize_plate_text(batch_results[2][0]) == normalize_plate_text(s2[0])


def test_sha256_verification_integrity(tmp_path):
    dummy_file = tmp_path / 'test_model.bin'
    dummy_file.write_bytes(b'SENTINELTRACK_OCR_MODEL_BYTES')
    correct_sha = compute_file_sha256(dummy_file)

    # Correct SHA passes
    assert verify_file_integrity(dummy_file, correct_sha) is True

    # Corrupted / Mismatched SHA raises ValueError
    with pytest.raises(ValueError, match='SHA-256 checksum mismatch'):
        verify_file_integrity(dummy_file, '0000000000000000000000000000000000000000000000000000000000000000')
