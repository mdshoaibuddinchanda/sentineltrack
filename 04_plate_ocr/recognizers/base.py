from abc import ABC, abstractmethod
import numpy as np


class BasePlateRecognizer(ABC):
    """Abstract interface for license plate text recognizers."""

    def __init__(self, model_name: str, device: str = 'cuda'):
        self.model_name = model_name
        self.device = device

    @abstractmethod
    def recognize(self, crop: np.ndarray) -> tuple[str, float, list[float]]:
        """
        Recognizes text directly from pre-located license plate crop.
        Returns:
            (raw_text: str, ocr_confidence: float, char_confidences: list[float])
        """
        pass

    def recognize_batch(self, crops: list[np.ndarray]) -> list[tuple[str, float, list[float]]]:
        """Batch recognition default fallback implementation."""
        return [self.recognize(c) for c in crops]
