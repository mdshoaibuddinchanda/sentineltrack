from .base import BasePlateRecognizer

__all__ = [
    'BasePlateRecognizer',
    'EasyOCRPlateRecognizer',
    'TrOCRPlateRecognizer',
    'PPOCRPlateRecognizer',
    'PPOCRMobilePlateRecognizer',
    'PPOCRServerPlateRecognizer',
    'AdaptivePlateRecognizer',
    'MockPlateRecognizer',
    'get_recognizer'
]


def get_recognizer(engine_name: str = 'ppocr_mobile', device: str = 'cpu') -> BasePlateRecognizer:
    """Factory creating the specified OCR recognizer instance with lazy imports."""
    engine_name = engine_name.lower()
    if 'mock' in engine_name:
        from .mock_rec import MockPlateRecognizer
        return MockPlateRecognizer()
    elif 'adaptive' in engine_name or 'cascade' in engine_name:
        from .paddle_rec import AdaptivePlateRecognizer
        return AdaptivePlateRecognizer(device=device)
    elif 'ppocr_mobile' in engine_name or 'mobile' in engine_name:
        from .paddle_rec import PPOCRMobilePlateRecognizer
        return PPOCRMobilePlateRecognizer(device=device)
    elif 'ppocr_server' in engine_name or 'server' in engine_name or 'paddle' in engine_name:
        from .paddle_rec import PPOCRServerPlateRecognizer
        return PPOCRServerPlateRecognizer(device=device)
    elif 'trocr' in engine_name:
        from .trocr_rec import TrOCRPlateRecognizer
        return TrOCRPlateRecognizer(device=device)
    elif 'easyocr_detect' in engine_name:
        from .easyocr_rec import EasyOCRPlateRecognizer
        return EasyOCRPlateRecognizer(device=device, model_name='easyocr_detect_rec', rec_only=False)
    elif 'easyocr' in engine_name or 'crnn' in engine_name:
        from .easyocr_rec import EasyOCRPlateRecognizer
        return EasyOCRPlateRecognizer(device=device, model_name='easyocr_rec_only', rec_only=True)
    else:
        from .paddle_rec import PPOCRMobilePlateRecognizer
        return PPOCRMobilePlateRecognizer(device=device)


def __getattr__(name: str):
    if name == 'EasyOCRPlateRecognizer':
        from .easyocr_rec import EasyOCRPlateRecognizer
        return EasyOCRPlateRecognizer
    elif name == 'TrOCRPlateRecognizer':
        from .trocr_rec import TrOCRPlateRecognizer
        return TrOCRPlateRecognizer
    elif name in ('PPOCRPlateRecognizer', 'PPOCRMobilePlateRecognizer', 'PPOCRServerPlateRecognizer', 'AdaptivePlateRecognizer'):
        from . import paddle_rec
        return getattr(paddle_rec, name)
    elif name == 'MockPlateRecognizer':
        from .mock_rec import MockPlateRecognizer
        return MockPlateRecognizer
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

