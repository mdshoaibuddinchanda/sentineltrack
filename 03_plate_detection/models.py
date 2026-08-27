from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlateObservation:
    camera_id: str
    track_id: int
    stream_epoch: int
    pts_ms: float
    confidence: float

    # Coordinates in ORIGINAL full CCTV frame
    x1: float
    y1: float
    x2: float
    y2: float

    # Plate dimensions in original frame
    width: float
    height: float

    # Associated vehicle information
    vehicle_class: str
    vehicle_confidence: float

    # Quality & visibility metrics
    plate_area: float = 0.0
    blur_score: float = 0.0
    brightness_score: float = 0.0
    quality_score: float = 0.0

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height > 0 else 0.0
