import torch
import numpy as np
from .base import BasePlateRecognizer


class EasyOCRPlateRecognizer(BasePlateRecognizer):
    """
    PyTorch-based CRNN/ResNet license plate text recognizer.
    Supports recognition-only mode (direct CRNN inference) and detect+recognize mode.
    """

    def __init__(
        self,
        device: str = 'cuda',
        model_name: str = 'easyocr_rec_only',
        rec_only: bool = True
    ):
        super().__init__(model_name=model_name, device=device)
        self.use_gpu = (device == 'cuda' or device == 'gpu') and torch.cuda.is_available()
        self.rec_only = rec_only
        self._reader = None

    def _get_reader(self):
        if self._reader is None:
            try:
                import easyocr
            except ImportError as e:
                raise RuntimeError("EasyOCR is not installed. Use PP-OCR recognizer or pip install easyocr.") from e
            self._reader = easyocr.Reader(['en'], gpu=self.use_gpu, verbose=False)
        return self._reader


    def recognize(self, crop: np.ndarray) -> tuple[str, float, list[float]]:
        if crop is None or crop.size == 0:
            return '', 0.0, []

        try:
            h, w = crop.shape[:2]
            reader = self._get_reader()

            if self.rec_only:
                # Direct Recognition-Only: pass full bounding box without CRAFT text detector
                horizontal_list = [[0, w, 0, h]]
                free_list = []
                results = reader.recognize(
                    crop,
                    horizontal_list=horizontal_list,
                    free_list=free_list,
                    allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                )
                if not results:
                    return '', 0.0, []

                sorted_res = sorted(results, key=lambda x: (x[0][0][1], x[0][0][0]))
                full_text = ''.join([r[1] for r in sorted_res])
                confidences = [float(r[2]) for r in sorted_res]
                avg_conf = float(np.mean(confidences)) if confidences else 0.0
                return full_text, round(avg_conf, 4), confidences

            else:
                # Detect + Recognize (CRAFT + CRNN)
                results = reader.readtext(
                    crop,
                    detail=1,
                    paragraph=False,
                    allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                )

                if not results:
                    return '', 0.0, []

                sorted_res = sorted(results, key=lambda x: (x[0][0][1], x[0][0][0]))
                full_text = ''.join([r[1] for r in sorted_res])
                confidences = [float(r[2]) for r in sorted_res]
                avg_conf = float(np.mean(confidences)) if confidences else 0.0
                return full_text, round(avg_conf, 4), confidences

        except Exception:
            return '', 0.0, []

    def recognize_batch(self, crops: list[np.ndarray]) -> list[tuple[str, float, list[float]]]:
        return [self.recognize(c) for c in crops]
