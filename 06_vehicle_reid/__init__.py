"""Priority 6: conservative vehicle-appearance ReID fallback."""

from .config import ReIDConfig
from .models import (
    AppearanceEvidence,
    ReIDCandidate,
    ReIDDecision,
    TrackKey,
    VehicleAppearanceEmbedding,
)
from .extractor import AppearanceEmbeddingExtractor, ReIDModelUnavailable
from .gallery import TrackEmbeddingGallery
from .matcher import ReIDMatcher
from .fusion import ReIDFusion, ReIDFusionResult
from .service import VehicleReIDService

__all__ = [
    "AppearanceEvidence",
    "AppearanceEmbeddingExtractor",
    "ReIDCandidate",
    "ReIDConfig",
    "ReIDDecision",
    "ReIDFusion",
    "ReIDFusionResult",
    "ReIDMatcher",
    "ReIDModelUnavailable",
    "TrackEmbeddingGallery",
    "TrackKey",
    "VehicleAppearanceEmbedding",
    "VehicleReIDService",
]
