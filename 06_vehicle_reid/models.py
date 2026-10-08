"""Typed evidence contracts for vehicle-appearance retrieval."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import numpy as np


class ReIDDecision(str, Enum):
    MATCH_SUPPORT = "MATCH_SUPPORT"
    REVIEW = "REVIEW"
    REJECTED = "REJECTED"


class AppearanceEvidence(str, Enum):
    STRONG_PLATE = "STRONG_PLATE"
    PARTIAL_PLATE = "PARTIAL_PLATE"
    NO_USABLE_PLATE = "NO_USABLE_PLATE"


@dataclass(frozen=True, order=True)
class TrackKey:
    """Stable cache key; stream epochs prevent reuse after a stream restart."""

    camera_id: str
    stream_epoch: int
    track_id: int


@dataclass
class VehicleAppearanceEmbedding:
    """One normalized appearance observation tied to a track and source event."""

    camera_id: str
    stream_epoch: int
    track_id: int
    embedding: np.ndarray
    model: str
    model_version: str
    crop_quality: float
    source_frame_metadata: dict[str, Any] = field(default_factory=dict)
    event_time_utc: Optional[datetime] = None
    plate_region_masked_for_reid: bool = True

    def __post_init__(self) -> None:
        vector = np.asarray(self.embedding, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vector))
        if vector.size == 0 or not np.isfinite(norm) or norm <= 1e-12:
            raise ValueError("Vehicle appearance embedding must be finite and non-zero")
        self.embedding = vector / norm
        self.crop_quality = float(np.clip(self.crop_quality, 0.0, 1.0))

    @property
    def track_key(self) -> TrackKey:
        return TrackKey(self.camera_id, self.stream_epoch, self.track_id)


@dataclass
class ReIDCandidate:
    """A pruned source-to-candidate appearance comparison."""

    source_track: TrackKey
    candidate_track: TrackKey
    cosine_similarity: float
    temporal_compatibility: float
    spatial_route_feasibility: Optional[float]
    reid_score: float
    decision: ReIDDecision
    reason: str
    source_event_time_utc: Optional[datetime] = None
    candidate_event_time_utc: Optional[datetime] = None
    vehicle_class: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrackProfile:
    """Bounded quality-crop accumulator and finalized track-level embedding."""

    key: TrackKey
    vehicle_class: Optional[str] = None
    first_event_time_utc: Optional[datetime] = None
    last_event_time_utc: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    observations: list[VehicleAppearanceEmbedding] = field(default_factory=list)
    embedding: Optional[np.ndarray] = None
    last_updated_monotonic: float = 0.0
