import os
import cv2
import numpy as np
import onnxruntime as ort
from pathlib import Path
from typing import Optional
from .base import BasePlateRecognizer

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = ROOT_DIR / 'models' / 'ocr'


def is_two_line_plate(crop: np.ndarray) -> bool:
    """Detects if crop is likely a two-line/motorcycle plate based on aspect ratio."""
    if crop is None or crop.size == 0:
        return False
    h, w = crop.shape[:2]
    aspect_ratio = float(w) / max(float(h), 1.0)
    # Standard single-line plates have aspect ratio > 2.8; two-line/square plates are ~1.2 to 2.2
    return 0.8 <= aspect_ratio <= 2.2


def split_two_line_plate(crop: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Splits a two-line plate into top and bottom line crops with overlap."""
    h, w = crop.shape[:2]
    mid = h // 2
    overlap = int(h * 0.08)
    top_crop = crop[0:min(h, mid + overlap), :]
    bot_crop = crop[max(0, mid - overlap):h, :]
    return top_crop, bot_crop


class PPOCRPlateRecognizer(BasePlateRecognizer):
    """
    ONNX-powered PaddleOCR (PP-OCRv5) Text Recognition Engine.
    Supports single-line, two-line motorcycle plates, and genuine tensor batching.
    """

    def __init__(
        self,
        model_path: str,
        dict_path: str,
        model_name: str = 'ppocr_mobile',
        device: str = 'cpu'
    ):
        super().__init__(model_name=model_name, device=device)
        self.model_path = Path(model_path)
        self.dict_path = Path(dict_path)

        if not self.model_path.exists():
            raise FileNotFoundError(f'PP-OCR model not found at: {self.model_path}')
        if not self.dict_path.exists():
            raise FileNotFoundError(f'PP-OCR dictionary not found at: {self.dict_path}')

        # Load character dictionary
        with open(self.dict_path, 'r', encoding='utf-8') as f:
            lines = [line.strip('\r\n') for line in f.readlines()]
        self.char_list = ['blank'] + lines + [' ']

        # Initialize ONNX session
        providers = ['CPUExecutionProvider']
        self.session = ort.InferenceSession(str(self.model_path), providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.target_height = 48

    def _preprocess_single(self, img: np.ndarray, target_w: Optional[int] = None) -> np.ndarray:
        h, w = img.shape[:2]
        scale = self.target_height / float(h)
        calc_w = max(int(w * scale), 16)

        if target_w is not None:
            resized = cv2.resize(img, (calc_w, self.target_height))
            # Pad to target_w
            padded = np.zeros((self.target_height, target_w, 3), dtype=np.uint8)
            padded[:, :min(calc_w, target_w)] = resized[:, :min(calc_w, target_w)]
            resized = padded
        else:
            resized = cv2.resize(img, (calc_w, self.target_height))

        inp = resized.astype(np.float32) / 255.0
        inp = (inp - 0.5) / 0.5
        inp = inp.transpose((2, 0, 1))  # [3, H, W]
        return inp

    def _ctc_decode(self, preds: np.ndarray) -> tuple[str, float, list[float]]:
        # preds: [T, num_classes]
        pred_indices = np.argmax(preds, axis=1)
        pred_probs = np.max(preds, axis=1)

        decoded_chars = []
        confs = []
        prev_idx = 0

        for idx, prob in zip(pred_indices, pred_probs):
            if idx != 0 and idx != prev_idx:
                if idx < len(self.char_list):
                    char = self.char_list[idx]
                    if char != ' ':
                        decoded_chars.append(char)
                        confs.append(float(prob))
            prev_idx = idx

        text = ''.join(decoded_chars).strip()
        avg_conf = float(np.mean(confs)) if confs else 0.0
        return text, round(avg_conf, 4), confs

    def recognize(self, crop: np.ndarray) -> tuple[str, float, list[float]]:
        if crop is None or crop.size == 0:
            return '', 0.0, []

        try:
            # Handle two-line / motorcycle plates
            if is_two_line_plate(crop):
                top_crop, bot_crop = split_two_line_plate(crop)
                top_txt, top_conf, top_confs = self.recognize_single_line(top_crop)
                bot_txt, bot_conf, bot_confs = self.recognize_single_line(bot_crop)
                combined_txt = top_txt + bot_txt
                combined_confs = top_confs + bot_confs
                avg_c = float(np.mean(combined_confs)) if combined_confs else 0.0
                return combined_txt, round(avg_c, 4), combined_confs

            return self.recognize_single_line(crop)

        except Exception:
            return '', 0.0, []

    def recognize_single_line(self, crop: np.ndarray) -> tuple[str, float, list[float]]:
        if crop is None or crop.size == 0:
            return '', 0.0, []

        inp = self._preprocess_single(crop)
        batch = np.expand_dims(inp, axis=0)  # [1, 3, H, W]

        outputs = self.session.run(None, {self.input_name: batch})
        preds = outputs[0][0]  # [T, num_classes]
        return self._ctc_decode(preds)

    def recognize_batch(self, crops: list[np.ndarray]) -> list[tuple[str, float, list[float]]]:
        """Performs GENUINE tensor batch inference."""
        if not crops:
            return []

        # Find max width
        preprocessed = []
        max_w = 16
        for c in crops:
            if c is None or c.size == 0:
                c = np.zeros((self.target_height, 64, 3), dtype=np.uint8)
            h, w = c.shape[:2]
            scale = self.target_height / float(h)
            cw = max(int(w * scale), 16)
            max_w = max(max_w, cw)

        # Build batched tensor [B, 3, 48, max_w]
        batch_list = [self._preprocess_single(c, target_w=max_w) for c in crops]
        batch_tensor = np.stack(batch_list, axis=0)

        outputs = self.session.run(None, {self.input_name: batch_tensor})
        batch_preds = outputs[0]  # [B, T, num_classes]

        results = []
        for i in range(len(crops)):
            res = self._ctc_decode(batch_preds[i])
            results.append(res)

        return results


class PPOCRMobilePlateRecognizer(PPOCRPlateRecognizer):
    def __init__(self, device: str = 'cpu'):
        super().__init__(
            model_path=str(MODELS_DIR / 'PP-OCRv5_mobile_rec_infer.onnx'),
            dict_path=str(MODELS_DIR / 'ppocr_mobile_dict.txt'),
            model_name='PP-OCRv5_mobile_rec',
            device=device
        )


class PPOCRServerPlateRecognizer(PPOCRPlateRecognizer):
    def __init__(self, device: str = 'cpu'):
        super().__init__(
            model_path=str(MODELS_DIR / 'PP-OCRv5_server_rec_infer.onnx'),
            dict_path=str(MODELS_DIR / 'ppocrv5_dict.txt'),
            model_name='PP-OCRv5_server_rec',
            device=device
        )
