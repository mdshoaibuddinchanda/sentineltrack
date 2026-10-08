"""Pruned cosine search for track-level vehicle appearance candidates."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

import numpy as np

from .config import ReIDConfig
from .gallery import TrackEmbeddingGallery
from .models import ReIDCandidate, ReIDDecision, TrackProfile, TrackKey, VehicleAppearanceEmbedding


RouteFeasibility = Callable[[TrackProfile, TrackProfile], Optional[float]]


def temporal_compatibility(
    source_time: Optional[datetime],
    candidate_time: Optional[datetime],
    window_seconds: float,
) -> tuple[float, Optional[str]]:
    """Return a chronological compatibility factor and an explicit rejection reason."""

    if source_time is None or candidate_time is None:
        # Unknown time is not positive evidence, but it should not erase an
        # otherwise useful review candidate. The caller still keeps the result
        # conservative through the fusion layer.
        return 1.0, None
    delta = (source_time - candidate_time).total_seconds()
    if delta < -1.0 or delta > window_seconds:
        return 0.0, "TEMPORALLY_INFEASIBLE"
    if window_seconds <= 0:
        return 1.0, None
    # A recent candidate is stronger; an old but feasible candidate is penalized.
    return max(0.10, 1.0 - (max(0.0, delta) / window_seconds) * 0.50), None


class ReIDMatcher:
    """Searches a bounded normalized matrix after metadata pruning."""

    def __init__(self, config: Optional[ReIDConfig] = None) -> None:
        self.config = config or ReIDConfig.from_yaml()

    def search(
        self,
        source: VehicleAppearanceEmbedding | TrackProfile,
        gallery: TrackEmbeddingGallery,
        *,
        vehicle_class: Optional[str] = None,
        top_k: int = 5,
        route_feasibility: Optional[RouteFeasibility] = None,
    ) -> list[ReIDCandidate]:
        source_key = source.track_key if isinstance(source, VehicleAppearanceEmbedding) else source.key
        source_vector = source.embedding if isinstance(source, VehicleAppearanceEmbedding) else source.embedding
        if source_vector is None:
            return []
        source_time = source.event_time_utc if isinstance(source, VehicleAppearanceEmbedding) else source.last_event_time_utc
        source_class = vehicle_class or (source.vehicle_class if isinstance(source, TrackProfile) else None)
        profiles, matrix = gallery.matrix()
        if not profiles:
            return []

        eligible: list[tuple[int, TrackProfile, float, float, Optional[str], Optional[float]]] = []
        for index, profile in enumerate(profiles):
            if profile.key == source_key:
                continue
            # A track ID is only meaningful inside its camera/epoch namespace.
            if profile.key.camera_id == source_key.camera_id:
                continue
            if self.config.require_class_compatibility and source_class and profile.vehicle_class:
                if source_class.lower() != profile.vehicle_class.lower():
                    continue
            temporal, time_reason = temporal_compatibility(
                source_time,
                profile.last_event_time_utc,
                self.config.search_time_window_seconds,
            )
            spatial: Optional[float] = None
            if time_reason is not None:
                eligible.append((index, profile, 0.0, temporal, time_reason, spatial))
                continue
            if route_feasibility is not None:
                result = route_feasibility(
                    source if isinstance(source, TrackProfile) else _profile_from_observation(source),
                    profile,
                )
                spatial = float(result) if result is not None else None
                if spatial is not None and spatial <= 0.0:
                    eligible.append((index, profile, 0.0, temporal, "ROUTE_INFEASIBLE", spatial))
                    continue
            eligible.append((index, profile, 0.0, temporal, None, spatial))

        if not eligible:
            return []
        eligible_indices = [row[0] for row in eligible if row[4] is None]
        if eligible_indices:
            similarities = matrix[eligible_indices] @ np.asarray(source_vector, dtype=np.float32)
            similarity_by_index = dict(zip(eligible_indices, similarities.tolist()))
        else:
            similarity_by_index = {}

        candidates: list[ReIDCandidate] = []
        for index, profile, _, temporal, rejection_reason, spatial in eligible:
            similarity = float(np.clip(similarity_by_index.get(index, 0.0), -1.0, 1.0))
            if rejection_reason == "TEMPORALLY_INFEASIBLE":
                score = 0.0
                decision = ReIDDecision.REJECTED
                reason = rejection_reason
            elif rejection_reason == "ROUTE_INFEASIBLE":
                score = 0.0
                decision = ReIDDecision.REJECTED
                reason = rejection_reason
            else:
                spatial_factor = 1.0 if spatial is None else float(np.clip(spatial, 0.0, 1.0))
                score = float(np.clip(similarity * temporal * spatial_factor, 0.0, 1.0))
                if score >= self.config.minimum_similarity_for_support:
                    if self.config.review_only:
                        decision = ReIDDecision.REVIEW
                        reason = "REID_HIGH_SIMILARITY_REVIEW_ONLY"
                    else:
                        decision = ReIDDecision.MATCH_SUPPORT
                        reason = "REID_HIGH_SIMILARITY"
                elif score >= self.config.minimum_similarity_for_review:
                    decision = ReIDDecision.REVIEW
                    reason = "REID_LOW_SIMILARITY"
                else:
                    decision = ReIDDecision.REJECTED
                    reason = "REID_LOW_SIMILARITY"
            candidates.append(
                ReIDCandidate(
                    source_track=source_key,
                    candidate_track=profile.key,
                    cosine_similarity=similarity,
                    temporal_compatibility=float(temporal),
                    spatial_route_feasibility=spatial,
                    reid_score=score,
                    decision=decision,
                    reason=reason,
                    source_event_time_utc=source_time,
                    candidate_event_time_utc=profile.last_event_time_utc,
                    vehicle_class=profile.vehicle_class,
                    metadata={"candidate_population_pruned": True},
                )
            )
        candidates.sort(key=lambda item: (item.reid_score, item.cosine_similarity), reverse=True)
        return candidates[: max(1, int(top_k))]


def _profile_from_observation(observation: VehicleAppearanceEmbedding) -> TrackProfile:
    return TrackProfile(
        key=observation.track_key,
        first_event_time_utc=observation.event_time_utc,
        last_event_time_utc=observation.event_time_utc,
        observations=[observation],
        embedding=observation.embedding,
    )
