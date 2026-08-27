from .base import BasePlateRecognizer
from .easyocr_rec import EasyOCRPlateRecognizer
from .trocr_rec import TrOCRPlateRecognizer
from .paddle_rec import PPOCRPlateRecognizer, PPOCRMobilePlateRecognizer, PPOCRServerPlateRecognizer
from .mock_rec import MockPlateRecognizer

__all__ = [
    'BasePlateRecognizer',
    'EasyOCRPlateRecognizer',
    'TrOCRPlateRecognizer',
    'PPOCRPlateRecognizer',
    'PPOCRMobilePlateRecognizer',
    'PPOCRServerPlateRecognizer',
    'MockPlateRecognizer',
    'get_recognizer'
]


def get_recognizer(engine_name: str = 'ppocr_server', device: str = 'cpu') -> BasePlateRecognizer:
    """Factory creating the specified OCR recognizer instance."""
    engine_name = engine_name.lower()
    if 'mock' in engine_name:
        return MockPlateRecognizer()
    elif 'ppocr_mobile' in engine_name or 'mobile' in engine_name:
        return PPOCRMobilePlateRecognizer(device=device)
    elif 'ppocr_server' in engine_name or 'server' in engine_name or 'paddle' in engine_name:
        return PPOCRServerPlateRecognizer(device=device)
    elif 'trocr' in engine_name:
        return TrOCRPlateRecognizer(device=device)
    elif 'easyocr_detect' in engine_name:
        return EasyOCRPlateRecognizer(device=device, model_name='easyocr_detect_rec', rec_only=False)
    elif 'easyocr' in engine_name or 'crnn' in engine_name:
        return EasyOCRPlateRecognizer(device=device, model_name='easyocr_rec_only', rec_only=True)
    else:
        return PPOCRServerPlateRecognizer(device=device)
