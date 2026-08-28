import torch
import cv2
import numpy as np
from typing import Optional
from .base import BasePlateRecognizer



class TrOCRPlateRecognizer(BasePlateRecognizer):
    """Transformer Vision-Encoder-Decoder Plate Recognizer with genuine confidence estimation."""

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

    def recognize(self, crop: np.ndarray) -> tuple[str, Optional[float], list[float]]:
        if crop is None or crop.size == 0:
            return '', None, []

        try:
            self._lazy_init()
            if len(crop.shape) == 2:
                rgb = cv2.cvtColor(crop, cv2.COLOR_GRAY2RGB)
            else:
                rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)

            from PIL import Image
            pil_img = Image.fromarray(rgb)
            pixel_values = self.processor(pil_img, return_tensors='pt').pixel_values.to(self.device)



            with torch.no_grad():
                gen_out = self.model.generate(
                    pixel_values,
                    max_new_tokens=16,
                    return_dict_in_generate=True,
                    output_scores=True
                )

            sequences = gen_out.sequences[0]
            text = self.processor.decode(sequences, skip_special_tokens=True).strip()

            # Calculate true token probabilities from generation scores
            scores = gen_out.scores  # list of [1, vocab_size] tensors
            char_probs = []
            if scores:
                for t, score_tensor in enumerate(scores):
                    probs = torch.softmax(score_tensor[0], dim=-1)
                    token_id = sequences[t + 1] if t + 1 < len(sequences) else torch.argmax(probs)
                    token_prob = float(probs[token_id].item())
                    char_probs.append(round(token_prob, 4))

            avg_conf = float(np.mean(char_probs)) if char_probs else None
            return text, avg_conf, char_probs

        except Exception:
            return '', None, []

    def recognize_batch(self, crops: list[np.ndarray]) -> list[tuple[str, Optional[float], list[float]]]:
        return [self.recognize(c) for c in crops]
