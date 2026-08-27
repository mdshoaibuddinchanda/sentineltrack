import numpy as np
from .base import BasePlateRecognizer


class MockPlateRecognizer(BasePlateRecognizer):
    """Deterministic Mock Recognizer for test suites and offline validation."""

    def __init__(self, default_text: str = 'GJ01AB1234', default_conf: float = 0.95):
        super().__init__(model_name='mock_rec', device='cpu')
        self.default_text = default_text
        self.default_conf = default_conf
        self.calls = 0

    def recognize(self, crop: np.ndarray) -> tuple[str, float, list[float]]:
        self.calls += 1
        if crop is None or crop.size == 0:
            return '', 0.0, []
        return self.default_text, self.default_conf, [self.default_conf] * len(self.default_text)
