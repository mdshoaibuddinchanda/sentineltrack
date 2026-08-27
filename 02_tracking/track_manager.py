import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from dataclasses import dataclass

import importlib
try:
    track_models = importlib.import_module("02_tracking.models")
    VehicleTrack = track_models.VehicleTrack
except Exception:
    from .models import VehicleTrack



@dataclass
class TrackState:
    track: VehicleTrack
    seen_frames: int = 1
    missed_frames: int = 0


class TrackManager:

    def __init__(self, max_trail_len: int = 30):
        self.tracks: dict[tuple[str, int, int], TrackState] = {}
        self.max_trail_len = max_trail_len

    def update(self, track: VehicleTrack) -> VehicleTrack:
        key = (
            track.camera_id,
            track.stream_epoch,
            track.track_id,
        )

        cx, cy = track.center

        if key not in self.tracks:
            track.trail = [(cx, cy)]
            track.age_frames = 1
            self.tracks[key] = TrackState(track=track)
            return track

        state = self.tracks[key]
        state.seen_frames += 1
        state.missed_frames = 0

        state.track.last_pts_ms = track.last_pts_ms
        state.track.confidence = track.confidence
        state.track.x1 = track.x1
        state.track.y1 = track.y1
        state.track.x2 = track.x2
        state.track.y2 = track.y2
        state.track.age_frames = state.seen_frames

        state.track.trail.append((cx, cy))
        if len(state.track.trail) > self.max_trail_len:
            state.track.trail = state.track.trail[-self.max_trail_len:]

        return state.track

    def reset_camera(self, camera_id: str):
        to_remove = [
            key for key in self.tracks
            if key[0] == camera_id
        ]
        for key in to_remove:
            del self.tracks[key]

    def get_active_tracks(self) -> list[VehicleTrack]:
        return [
            state.track for state in self.tracks.values()
        ]

    def get_camera_tracks(self, camera_id: str, stream_epoch: int | None = None) -> list[VehicleTrack]:
        return [
            state.track for key, state in self.tracks.items()
            if key[0] == camera_id and (stream_epoch is None or key[1] == stream_epoch)
        ]
