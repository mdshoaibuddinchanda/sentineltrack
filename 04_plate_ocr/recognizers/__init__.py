from .base import BasePlateRecognizer
from .easyocr_rec import EasyOCRPlateRecognizer
from .trocr_rec import TrOCRPlateRecognizer
from .mock_rec import MockPlateRecognizer

__all__ = [
    'BasePlateRecognizer',
    'EasyOCRPlateRecognizer',
    'TrOCRPlateRecognizer',
    'MockPlateRecognizer',
    'get_recognizer'
]


def get_recognizer(engine_name: str = 'easyocr_crnn', device: str = 'cuda') -> BasePlateRecognizer:
    """Factory creating the specified OCR recognizer instance."""
    engine_name = engine_name.lower()
    if 'mock' in engine_name:
        return MockPlateRecognizer()
    elif 'trocr' in engine_name:
        return TrOCRPlateRecognizer(device=device)
    elif 'easyocr' in engine_name or 'crnn' in engine_name:
        return EasyOCRPlateRecognizer(device=device)
    else:
        return EasyOCRPlateRecognizer(device=device)
