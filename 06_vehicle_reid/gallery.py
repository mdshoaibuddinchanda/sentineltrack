"""Bounded track-level appearance gallery with epoch-safe cache keys."""

from __future__ import annotations

import time
from collections import OrderedDict
from datetime import datetime
from typing import Iterable, Optional

import numpy as np

from .config import ReIDConfig
from .models import TrackKey, TrackProfile, VehicleAppearanceEmbedding


class TrackEmbeddingGallery:
    """Stores one robust embedding per track, not one embedding per frame."""

    def __init__(
        self,
        config: Optional[ReIDConfig] = None,
        *,
        max_tracks: Optional[int] = None,
        ttl_seconds: Optional[float] = None,
        top_k_crops: Optional[int] = None,
    ) -> None:
        self.config = config or ReIDConfig.from_yaml()
        self.max_tracks = max_tracks or self.config.gallery_max_tracks
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else self.config.gallery_ttl_seconds
        self.top_k_crops = top_k_crops or self.config.top_k_crops_per_track
        self._profiles: "OrderedDict[TrackKey, TrackProfile]" = OrderedDict()

    def _prune(self, now: Optional[float] = None) -> None:
        current = now if now is not None else time.monotonic()
        expired = [
            key
            for key, profile in self._profiles.items()
            if profile.last_updated_monotonic and current - profile.last_updated_monotonic > self.ttl_seconds
        ]
        for key in expired:
            self._profiles.pop(key, None)

    def add_observation(
        self,
        observation: VehicleAppearanceEmbedding,
        *,
        vehicle_class: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> TrackProfile:
        """Add a quality-ranked crop and update one track-level aggregate."""

        now = time.monotonic()
        self._prune(now)
        key = observation.track_key
        profile = self._profiles.get(key)
        if profile is None:
            profile = TrackProfile(key=key)
            self._profiles[key] = profile
        self._profiles.move_to_end(key)
        profile.last_updated_monotonic = now
        if vehicle_class:
            profile.vehicle_class = vehicle_class
        if latitude is not None:
            profile.latitude = latitude
        if longitude is not None:
            profile.longitude = longitude
        profile.observations.append(observation)
        profile.observations.sort(key=lambda item: item.crop_quality, reverse=True)
        del profile.observations[self.top_k_crops :]
        times = [item.event_time_utc for item in profile.observations if item.event_time_utc is not None]
        if times:
            profile.first_event_time_utc = min(times)
            profile.last_event_time_utc = max(times)
        profile.embedding = self._aggregate(profile.observations)
        while len(self._profiles) > self.max_tracks:
            self._profiles.popitem(last=False)
        return profile

    @staticmethod
    def _aggregate(observations: Iterable[VehicleAppearanceEmbedding]) -> Optional[np.ndarray]:
        vectors = [item.embedding for item in observations]
        if not vectors:
            return None
        aggregate = np.mean(np.stack(vectors), axis=0).astype(np.float32)
        norm = float(np.linalg.norm(aggregate))
        return aggregate / norm if norm > 1e-12 else None

    def get(self, key: TrackKey) -> Optional[TrackProfile]:
        self._prune()
        profile = self._profiles.get(key)
        if profile is not None:
            self._profiles.move_to_end(key)
        return profile

    def profiles(self) -> list[TrackProfile]:
        self._prune()
        return list(self._profiles.values())

    def finalized(self) -> list[TrackProfile]:
        """Return only tracks with a usable aggregate embedding."""

        return [profile for profile in self.profiles() if profile.embedding is not None]

    def matrix(self) -> tuple[list[TrackProfile], np.ndarray]:
        profiles = self.finalized()
        if not profiles:
            return [], np.empty((0, 0), dtype=np.float32)
        return profiles, np.stack([profile.embedding for profile in profiles]).astype(np.float32)

    def clear(self) -> None:
        self._profiles.clear()

    def __len__(self) -> int:
        self._prune()
        return len(self._profiles)
