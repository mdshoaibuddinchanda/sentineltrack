from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OCRHypothesis:
    """Represents a single frame OCR observation hypothesis for a vehicle track."""
    camera_id: str
    track_id: int
    stream_epoch: int
    pts_ms: float
    raw_text: str
    normalized_text: str
    ocr_confidence: float
    crop_quality: float
    grammar_score: float
    preprocess_variant: str = 'raw'
    recognizer_name: str = 'default'
    character_confidences: list[float] = field(default_factory=list)
    plate_width: int = 0
    plate_height: int = 0

    @property
    def weighted_score(self) -> float:
        """Composite quality and confidence score."""
        return (
            0.50 * self.ocr_confidence +
            0.30 * self.grammar_score +
            0.20 * self.crop_quality
        )


@dataclass
class TrackOCRResult:
    """Represents the multi-frame consensus OCR resolution for a vehicle track."""
    camera_id: str
    track_id: int
    stream_epoch: int
    first_pts_ms: float
    last_pts_ms: float
    best_text: Optional[str]
    confidence: float
    support_count: int
    total_hypotheses: int
    status: str  # 'RESOLVED' | 'LOW_CONFIDENCE' | 'INSUFFICIENT_EVIDENCE'
    alternatives: list[tuple[str, float]] = field(default_factory=list)
    hypotheses: list[OCRHypothesis] = field(default_factory=list)

    @property
    def is_resolved(self) -> bool:
        return self.status == 'RESOLVED' and self.best_text is not None and len(self.best_text) >= 6
