import torch
import cv2
import numpy as np
from PIL import Image
from .base import BasePlateRecognizer


class TrOCRPlateRecognizer(BasePlateRecognizer):
    """Transformer Vision-Encoder-Decoder Plate Recognizer."""

    def __init__(self, device: str = 'cuda', model_name: str = 'microsoft/trocr-small-printed'):
        super().__init__(model_name=model_name, device=device)
        self.device = 'cuda' if torch.cuda.is_available() and device in ('cuda', 'gpu') else 'cpu'
        self.processor = None
        self.model = None
        self._initialized = False

    def _lazy_init(self):
        if not self._initialized:
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel
            self.processor = TrOCRProcessor.from_pretrained(self.model_name)
            self.model = VisionEncoderDecoderModel.from_pretrained(self.model_name).to(self.device)
            self.model.eval()
            self._initialized = True

    def recognize(self, crop: np.ndarray) -> tuple[str, float, list[float]]:
        if crop is None or crop.size == 0:
            return '', 0.0, []

        try:
            self._lazy_init()
            if len(crop.shape) == 2:
                rgb = cv2.cvtColor(crop, cv2.COLOR_GRAY2RGB)
            else:
                rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)

            pil_img = Image.fromarray(rgb)
            pixel_values = self.processor(pil_img, return_tensors='pt').pixel_values.to(self.device)

            with torch.no_grad():
                generated_ids = self.model.generate(pixel_values, max_new_tokens=16)

            text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            confidence = 0.85 if len(text.strip()) >= 6 else 0.40
            return text.strip(), confidence, [confidence]

        except Exception as e:
            return '', 0.0, []

    def recognize_batch(self, crops: list[np.ndarray]) -> list[tuple[str, float, list[float]]]:
        return [self.recognize(c) for c in crops]
