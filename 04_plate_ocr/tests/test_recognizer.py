import importlib
import numpy as np

rec_mod = importlib.import_module('04_plate_ocr.recognizers')
mock_mod = importlib.import_module('04_plate_ocr.recognizers.mock_rec')

get_recognizer = rec_mod.get_recognizer
MockPlateRecognizer = mock_mod.MockPlateRecognizer


def test_mock_recognizer():
    mock = MockPlateRecognizer(default_text='MH12DE1432', default_conf=0.96)
    dummy = np.full((64, 256, 3), 255, dtype=np.uint8)
    text, conf, chars = mock.recognize(dummy)
    assert text == 'MH12DE1432'
    assert conf == 0.96
    assert mock.calls == 1


def test_recognizer_factory():
    rec_mock = get_recognizer('mock_rec')
    assert isinstance(rec_mock, MockPlateRecognizer)
