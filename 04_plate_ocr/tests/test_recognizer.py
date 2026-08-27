import importlib
import numpy as np

rec_mod = importlib.import_module('04_plate_ocr.recognizers')
paddle_mod = importlib.import_module('04_plate_ocr.recognizers.paddle_rec')
mock_mod = importlib.import_module('04_plate_ocr.recognizers.mock_rec')

get_recognizer = rec_mod.get_recognizer
is_two_line_plate = paddle_mod.is_two_line_plate
split_two_line_plate = paddle_mod.split_two_line_plate
MockPlateRecognizer = mock_mod.MockPlateRecognizer


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
    assert rec_mobile.model_name == 'PP-OCRv5_mobile_rec'


def test_ppocr_mobile_single_and_batch_inference():
    rec = get_recognizer('ppocr_mobile', device='cpu')
    dummy1 = np.full((48, 160, 3), 240, dtype=np.uint8)
    dummy2 = np.full((48, 200, 3), 200, dtype=np.uint8)

    t1, c1, _ = rec.recognize(dummy1)
    batch_res = rec.recognize_batch([dummy1, dummy2])
    assert len(batch_res) == 2
    assert isinstance(batch_res[0][0], str)
    assert isinstance(batch_res[1][0], str)


def test_two_line_plate_detection_and_split():
    # Square/motorcycle plate: 100x120 (aspect ratio 1.2)
    two_line_crop = np.zeros((100, 120, 3), dtype=np.uint8)
    assert is_two_line_plate(two_line_crop) is True

    # Standard single line plate: 40x160 (aspect ratio 4.0)
    single_line_crop = np.zeros((40, 160, 3), dtype=np.uint8)
    assert is_two_line_plate(single_line_crop) is False

    top_crop, bot_crop = split_two_line_plate(two_line_crop)
    assert top_crop.shape[0] > 40
    assert bot_crop.shape[0] > 40
