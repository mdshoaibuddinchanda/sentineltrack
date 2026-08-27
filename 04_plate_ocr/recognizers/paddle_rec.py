import os
import cv2
import math
import importlib
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
    return 0.8 <= aspect_ratio <= 1.85


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
        model_name: str = 'en_PP-OCRv5_mobile_rec_onnx',
        device: str = 'cpu'
    ):
        super().__init__(model_name=model_name, device=device)
        self.model_path = Path(model_path)
        self.dict_path = Path(dict_path)

        if not self.model_path.exists():
            raise FileNotFoundError(f'PP-OCR model not found at: {self.model_path}')
        if not self.dict_path.exists():
            raise FileNotFoundError(f'PP-OCR dictionary not found at: {self.dict_path}')

        with open(self.dict_path, 'r', encoding='utf-8') as f:
            lines = [line.strip('\r\n') for line in f.readlines()]
        self.char_list = ['blank'] + lines + [' ']

        avail_providers = ort.get_available_providers()
        if (device == 'cuda' or device == 'gpu') and 'CUDAExecutionProvider' in avail_providers:
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            self.active_provider = 'CUDA'
        else:
            providers = ['CPUExecutionProvider']
            self.active_provider = 'CPU'

        self.session = ort.InferenceSession(str(self.model_path), providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.target_height = 48

    def _preprocess_single(self, img: np.ndarray, target_w: Optional[int] = None) -> tuple[np.ndarray, int]:
        h, w = img.shape[:2]
        scale = self.target_height / float(max(h, 1))
        # Ensure calculated width is always a positive multiple of 8
        calc_w = max(16, int(math.ceil(w * scale / 8.0) * 8))
        resized = cv2.resize(img, (calc_w, self.target_height))

        if target_w is not None and target_w > calc_w:
            pad_w = target_w - calc_w
            padded = cv2.copyMakeBorder(resized, 0, 0, 0, pad_w, cv2.BORDER_REPLICATE)
        else:
            padded = resized

        inp = padded.astype(np.float32) / 255.0
        inp = (inp - 0.5) / 0.5
        inp = inp.transpose((2, 0, 1))  # [3, H, W]
        return inp, calc_w

    def _ctc_decode(self, preds: np.ndarray) -> tuple[str, Optional[float], list[float]]:
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
        avg_conf = float(np.mean(confs)) if confs else None
        return text, round(avg_conf, 4) if avg_conf is not None else None, confs

    def recognize(self, crop: np.ndarray) -> tuple[str, Optional[float], list[float]]:
        if crop is None or crop.size == 0:
            return '', None, []

        try:
            if is_two_line_plate(crop):
                top_crop, bot_crop = split_two_line_plate(crop)
                top_txt, top_conf, top_confs = self.recognize_single_line(top_crop)
                bot_txt, bot_conf, bot_confs = self.recognize_single_line(bot_crop)
                combined_txt = top_txt + bot_txt
                combined_confs = top_confs + bot_confs
                avg_c = float(np.mean(combined_confs)) if combined_confs else None
                return combined_txt, round(avg_c, 4) if avg_c is not None else None, combined_confs

            return self.recognize_single_line(crop)

        except Exception:
            return '', None, []

    def recognize_single_line(self, crop: np.ndarray) -> tuple[str, Optional[float], list[float]]:
        if crop is None or crop.size == 0:
            return '', None, []

        inp, _ = self._preprocess_single(crop)
        batch = np.expand_dims(inp, axis=0)  # [1, 3, H, W]

        outputs = self.session.run(None, {self.input_name: batch})
        preds = outputs[0][0]  # [T, num_classes]
        return self._ctc_decode(preds)

    def _infer_flat_tensor_batch(self, crops_list: list[np.ndarray]) -> list[tuple[str, Optional[float], list[float]]]:
        if not crops_list:
            return []

        max_w = 16
        cws = []
        for c in crops_list:
            if c is None or c.size == 0:
                c = np.zeros((self.target_height, 64, 3), dtype=np.uint8)
            h, w = c.shape[:2]
            scale = self.target_height / float(max(h, 1))
            cw = max(16, int(math.ceil(w * scale / 8.0) * 8))
            cws.append(cw)
            max_w = max(max_w, cw)

        batch_list = [self._preprocess_single(c, target_w=max_w)[0] for c in crops_list]
        batch_tensor = np.stack(batch_list, axis=0)

        outputs = self.session.run(None, {self.input_name: batch_tensor})
        batch_preds = outputs[0]  # [B, T, num_classes]

        results = []
        for i in range(len(crops_list)):
            t_valid = max(1, cws[i] // 8)
            results.append(self._ctc_decode(batch_preds[i, :t_valid, :]))
        return results

    def recognize_batch(self, crops: list[np.ndarray]) -> list[tuple[str, Optional[float], list[float]]]:
        """
        Performs GENUINE tensor batch inference with two-line layout parity.
        Splits two-line crops, batches all line segments together, and reassembles them in order.
        """
        if not crops:
            return []

        flat_crops_to_infer = []
        layout_map = []

        for i, crop in enumerate(crops):
            if crop is None or crop.size == 0:
                flat_idx = len(flat_crops_to_infer)
                flat_crops_to_infer.append(np.zeros((self.target_height, 64, 3), dtype=np.uint8))
                layout_map.append(('empty', flat_idx))
            elif is_two_line_plate(crop):
                top_crop, bot_crop = split_two_line_plate(crop)
                top_idx = len(flat_crops_to_infer)
                flat_crops_to_infer.append(top_crop)
                bot_idx = len(flat_crops_to_infer)
                flat_crops_to_infer.append(bot_crop)
                layout_map.append(('two_line', top_idx, bot_idx))
            else:
                flat_idx = len(flat_crops_to_infer)
                flat_crops_to_infer.append(crop)
                layout_map.append(('single', flat_idx))

        flat_results = self._infer_flat_tensor_batch(flat_crops_to_infer)

        final_results = []
        for item in layout_map:
            kind = item[0]
            if kind == 'empty':
                final_results.append(('', None, []))
            elif kind == 'single':
                final_results.append(flat_results[item[1]])
            elif kind == 'two_line':
                top_res = flat_results[item[1]]
                bot_res = flat_results[item[2]]
                comb_txt = top_res[0] + bot_res[0]
                comb_confs = top_res[2] + bot_res[2]
                avg_c = float(np.mean(comb_confs)) if comb_confs else None
                final_results.append((comb_txt, round(avg_c, 4) if avg_c is not None else None, comb_confs))

        return final_results


class PPOCRMobilePlateRecognizer(PPOCRPlateRecognizer):
    def __init__(self, device: str = 'cpu'):
        super().__init__(
            model_path=str(MODELS_DIR / 'PP-OCRv5_mobile_rec_infer.onnx'),
            dict_path=str(MODELS_DIR / 'ppocr_mobile_dict.txt'),
            model_name='en_PP-OCRv5_mobile_rec_onnx',
            device=device
        )


class PPOCRServerPlateRecognizer(PPOCRPlateRecognizer):
    def __init__(self, device: str = 'cpu'):
        super().__init__(
            model_path=str(MODELS_DIR / 'PP-OCRv5_server_rec_infer.onnx'),
            dict_path=str(MODELS_DIR / 'ppocrv5_dict.txt'),
            model_name='PP-OCRv5_server_rec_onnx',
            device=device
        )


class AdaptivePlateRecognizer(BasePlateRecognizer):
    """
    Two-Stage Adaptive Cascade Recognizer:
    Runs fast Mobile recognizer first; falls back to Server model on uncertain predictions.
    """

    def __init__(
        self,
        min_conf_threshold: float = 0.85,
        min_grammar_threshold: float = 0.70,
        device: str = 'cpu'
    ):
        super().__init__(model_name='adaptive_mobile_server_cascade_onnx', device=device)
        self.mobile = PPOCRMobilePlateRecognizer(device=device)
        self.server = PPOCRServerPlateRecognizer(device=device)
        self.min_conf_threshold = min_conf_threshold
        self.min_grammar_threshold = min_grammar_threshold

        self.total_invocations = 0
        self.server_fallbacks = 0

        gram_mod = importlib.import_module('04_plate_ocr.grammar')
        self.score_grammar = gram_mod.score_indian_grammar

    def recognize(self, crop: np.ndarray) -> tuple[str, Optional[float], list[float]]:
        self.total_invocations += 1
        if crop is None or crop.size == 0:
            return '', None, []

        mob_txt, mob_conf, mob_confs = self.mobile.recognize(crop)
        norm_txt = mob_txt.replace(' ', '').upper()
        gram_sc = self.score_grammar(norm_txt)

        needs_fallback = (
            (mob_conf is not None and mob_conf < self.min_conf_threshold) or
            (gram_sc < self.min_grammar_threshold) or
            (len(norm_txt) < 8 or len(norm_txt) > 11)
        )

        if needs_fallback:
            self.server_fallbacks += 1
            srv_txt, srv_conf, srv_confs = self.server.recognize(crop)
            srv_norm = srv_txt.replace(' ', '').upper()
            srv_gram = self.score_grammar(srv_norm)

            if srv_gram >= gram_sc or (srv_conf or 0) > (mob_conf or 0):
                return srv_txt, srv_conf, srv_confs

        return mob_txt, mob_conf, mob_confs

    def recognize_batch(self, crops: list[np.ndarray]) -> list[tuple[str, Optional[float], list[float]]]:
        return [self.recognize(c) for c in crops]

    @property
    def fallback_rate(self) -> float:
        return self.server_fallbacks / max(self.total_invocations, 1)
