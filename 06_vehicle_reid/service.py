"""Conditional P6 service used beside, never instead of, P5 ANPR matching."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Sequence

import numpy as np

from .config import ReIDConfig
from .extractor import AppearanceEmbeddingExtractor, ReIDModelUnavailable
from .fusion import ReIDFusion, ReIDFusionResult
from .gallery import TrackEmbeddingGallery
from .matcher import ReIDMatcher, RouteFeasibility
from .models import AppearanceEvidence, ReIDCandidate, TrackKey, TrackProfile, VehicleAppearanceEmbedding


@dataclass
class ReIDProcessResult:
    track_key: TrackKey
    ran: bool
    stored: bool
    model_available: bool
    skip_reason: Optional[str] = None
    profile: Optional[TrackProfile] = None
    candidates: list[ReIDCandidate] | None = None
    error: Optional[str] = None


class VehicleReIDService:
    """Track-aware appearance fallback with bounded compute and graceful failure."""

    def __init__(
        self,
        config: Optional[ReIDConfig] = None,
        *,
        extractor: Optional[AppearanceEmbeddingExtractor] = None,
        gallery: Optional[TrackEmbeddingGallery] = None,
        matcher: Optional[ReIDMatcher] = None,
        fusion: Optional[ReIDFusion] = None,
    ) -> None:
        self.config = config or ReIDConfig.from_yaml()
        self.extractor = extractor or AppearanceEmbeddingExtractor(self.config)
        self.gallery = gallery or TrackEmbeddingGallery(self.config)
        self.matcher = matcher or ReIDMatcher(self.config)
        self.fusion = fusion or ReIDFusion(self.config)

    @staticmethod
    def _evidence(value: AppearanceEvidence | str | None) -> Optional[AppearanceEvidence]:
        if value is None:
            return None
        if isinstance(value, AppearanceEvidence):
            return value
        return AppearanceEvidence(str(value))

    def should_run_reid(self, evidence_level: AppearanceEvidence | str | None) -> tuple[bool, str]:
        evidence = self._evidence(evidence_level)
        if not self.config.enabled:
            return False, "REID_DISABLED"
        if evidence == AppearanceEvidence.STRONG_PLATE:
            return False, "ANPR_STRONG_REID_NOT_REQUIRED"
        if evidence in (AppearanceEvidence.PARTIAL_PLATE, AppearanceEvidence.NO_USABLE_PLATE, None):
            return True, "CONDITIONAL_PARTIAL_OR_NO_PLATE"
        return True, "CONDITIONAL_APPEARANCE_FALLBACK"

    def add_track_crop(
        self,
        track: Any,
        crop: Optional[np.ndarray],
        *,
        plate_bbox: Optional[Sequence[float]] = None,
        evidence_level: AppearanceEvidence | str | None = None,
        event_time_utc: Optional[datetime] = None,
        source_frame_metadata: Optional[dict[str, Any]] = None,
        crop_quality: Optional[float] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> ReIDProcessResult:
        key = TrackKey(str(track.camera_id), int(track.stream_epoch), int(track.track_id))
        should_run, reason = self.should_run_reid(evidence_level)
        if not should_run:
            return ReIDProcessResult(key, False, False, self.extractor.is_available, skip_reason=reason)
        try:
            observation = self.extractor.extract(
                crop,
                camera_id=key.camera_id,
                stream_epoch=key.stream_epoch,
                track_id=key.track_id,
                event_time_utc=event_time_utc,
                plate_bbox=plate_bbox,
                crop_quality=crop_quality,
                source_frame_metadata=source_frame_metadata,
            )
        except ReIDModelUnavailable as exc:
            # ANPR remains operational when the optional fallback model is absent.
            return ReIDProcessResult(key, True, False, False, error=str(exc))
        except (TypeError, ValueError, OSError) as exc:
            return ReIDProcessResult(key, True, False, self.extractor.is_available, error=str(exc))
        if observation is None:
            return ReIDProcessResult(key, True, False, self.extractor.is_available, skip_reason="INVALID_OR_TINY_CROP")
        if observation.crop_quality < self.config.minimum_crop_quality:
            return ReIDProcessResult(key, True, False, True, skip_reason="LOW_QUALITY_CROP")
        profile = self.gallery.add_observation(
            observation,
            vehicle_class=getattr(track, "class_name", None),
            latitude=latitude,
            longitude=longitude,
        )
        return ReIDProcessResult(key, True, True, True, profile=profile)

    def search_track(
        self,
        key: TrackKey,
        *,
        top_k: int = 5,
        route_feasibility: Optional[RouteFeasibility] = None,
    ) -> list[ReIDCandidate]:
        profile = self.gallery.get(key)
        if profile is None:
            return []
        return self.matcher.search(
            profile,
            self.gallery,
            top_k=top_k,
            route_feasibility=route_feasibility,
        )

    def fuse_p5_candidate(
        self,
        p5_candidate: Optional[object],
        reid_candidate: Optional[ReIDCandidate] = None,
        *,
        evidence_level: AppearanceEvidence | str | None = None,
    ) -> ReIDFusionResult:
        return self.fusion.fuse(
            p5_candidate,
            reid_candidate,
            evidence_level=self._evidence(evidence_level),
        )
