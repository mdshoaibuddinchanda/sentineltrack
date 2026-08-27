import cv2
import hashlib
import importlib
import numpy as np
from typing import Optional

from .models import OCRHypothesis, TrackOCRResult
from .preprocess import preprocess_crop
from .normalization import normalize_plate_text
from .grammar import score_indian_grammar
from .voting import MultiFramePlateVoter
from .recognizers import get_recognizer, BasePlateRecognizer

# Cross-package dynamic imports
fnd_models = importlib.import_module('00_foundation.streams.models')
p3_models = importlib.import_module('03_plate_detection.models')
p3_quality = importlib.import_module('03_plate_detection.quality')

FramePacket = fnd_models.FramePacket
PlateObservation = p3_models.PlateObservation
TrackPlateAccumulator = p3_quality.TrackPlateAccumulator


def compute_crop_hash(crop: np.ndarray) -> str:
    """Computes fast MD5 perceptual hash of downsampled crop for deduplication."""
    if crop is None or crop.size == 0:
        return ''
    small = cv2.resize(crop, (16, 8), interpolation=cv2.INTER_AREA)
    return hashlib.md5(small.tobytes()).hexdigest()


class PlateOCRPipeline:
    """End-to-end Priority 4 OCR & multi-frame consensus pipeline."""

    def __init__(
        self,
        recognizer: Optional[BasePlateRecognizer] = None,
        voter: Optional[MultiFramePlateVoter] = None,
        default_variant: str = 'raw',
        enable_deduplication: bool = True,
        min_crop_quality: float = 0.20,
    ):
        self.recognizer = recognizer or get_recognizer(engine_name='ppocr_mobile', device='cpu')
        self.voter = voter or MultiFramePlateVoter(min_crop_quality=min_crop_quality, min_support_count=2)
        self.default_variant = default_variant
        self.enable_deduplication = enable_deduplication
        self.min_crop_quality = min_crop_quality

        self.track_hypotheses: dict[tuple[str, int, int], list[OCRHypothesis]] = {}
        self.seen_crop_hashes: dict[tuple[str, int, int], set[str]] = {}

    def recognize_crop(
        self,
        crop: np.ndarray,
        camera_id: str,
        track_id: int,
        stream_epoch: int,
        pts_ms: float,
        crop_quality: float = 0.50,
        variant: Optional[str] = None
    ) -> OCRHypothesis:
        var = variant or self.default_variant
        prep_img, prep_meta = preprocess_crop(crop, variant=var, target_height=48)

        raw_text, ocr_conf, char_confs = self.recognizer.recognize(prep_img)
        norm_text = normalize_plate_text(raw_text)
        grammar_sc = score_indian_grammar(norm_text)

        h, w = crop.shape[:2] if crop is not None and crop.size > 0 else (0, 0)

        return OCRHypothesis(
            camera_id=camera_id,
            track_id=track_id,
            stream_epoch=stream_epoch,
            pts_ms=pts_ms,
            raw_text=raw_text,
            normalized_text=norm_text,
            ocr_confidence=ocr_conf if ocr_conf is not None else 0.5,
            crop_quality=crop_quality,
            grammar_score=grammar_sc,
            preprocess_variant=var,
            recognizer_name=self.recognizer.model_name,
            character_confidences=char_confs,
            plate_width=w,
            plate_height=h
        )

    def process_observation(
        self,
        observation: PlateObservation,
        crop_image: np.ndarray
    ) -> Optional[OCRHypothesis]:
        key = (observation.camera_id, observation.stream_epoch, observation.track_id)

        if key not in self.track_hypotheses:
            self.track_hypotheses[key] = []
            self.seen_crop_hashes[key] = set()

        if self.enable_deduplication:
            c_hash = compute_crop_hash(crop_image)
            if c_hash in self.seen_crop_hashes[key]:
                return None
            self.seen_crop_hashes[key].add(c_hash)

        if observation.quality_score < self.min_crop_quality * 0.75:
            return None

        hyp = self.recognize_crop(
            crop=crop_image,
            camera_id=observation.camera_id,
            track_id=observation.track_id,
            stream_epoch=observation.stream_epoch,
            pts_ms=observation.pts_ms,
            crop_quality=observation.quality_score,
            variant=self.default_variant
        )
        self.track_hypotheses[key].append(hyp)
        return hyp

    def get_track_result(self, camera_id: str, stream_epoch: int, track_id: int) -> TrackOCRResult:
        key = (camera_id, stream_epoch, track_id)
        hyps = self.track_hypotheses.get(key, [])
        return self.voter.vote(hyps)

    def reset_camera(self, camera_id: str):
        to_remove = [k for k in self.track_hypotheses if k[0] == camera_id]
        for k in to_remove:
            del self.track_hypotheses[k]
            if k in self.seen_crop_hashes:
                del self.seen_crop_hashes[k]
