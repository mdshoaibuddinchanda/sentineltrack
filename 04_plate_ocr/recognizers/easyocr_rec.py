import easyocr
import numpy as np
from .base import BasePlateRecognizer


class EasyOCRPlateRecognizer(BasePlateRecognizer):
    """PyTorch-based CRNN/ResNet license plate text recognizer."""

    def __init__(self, device: str = 'cuda', model_name: str = 'easyocr_crnn'):
        super().__init__(model_name=model_name, device=device)
        use_gpu = (device == 'cuda' or device == 'gpu')
        self.reader = easyocr.Reader(['en'], gpu=use_gpu, verbose=False)

    def recognize(self, crop: np.ndarray) -> tuple[str, float, list[float]]:
        if crop is None or crop.size == 0:
            return '', 0.0, []

        try:
            results = self.reader.readtext(
                crop,
                detail=1,
                paragraph=False,
                allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            )
            if not results:
                results = self.reader.readtext(crop, detail=1, paragraph=False)

            if not results:
                return '', 0.0, []

            sorted_res = sorted(results, key=lambda x: (x[0][0][1], x[0][0][0]))
            full_text = ''.join([r[1] for r in sorted_res])
            confidences = [float(r[2]) for r in sorted_res]
            avg_conf = float(np.mean(confidences)) if confidences else 0.0

            return full_text, round(avg_conf, 4), confidences

        except Exception as e:
            return '', 0.0, []

    def recognize_batch(self, crops: list[np.ndarray]) -> list[tuple[str, float, list[float]]]:
        return [self.recognize(c) for c in crops]
