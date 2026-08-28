import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import torch
import numpy as np
from ultralytics.trackers.byte_tracker import BYTETracker

import importlib
try:
    track_models = importlib.import_module("02_tracking.models")
    VehicleTrack = track_models.VehicleTrack
except Exception:
    from .models import VehicleTrack


import importlib
try:
    det_models = importlib.import_module('01_vehicle_detection.models')
    VehicleDetection = det_models.VehicleDetection
    det_classes = importlib.import_module('01_vehicle_detection.detector')
    VEHICLE_CLASSES = det_classes.VEHICLE_CLASSES
except Exception:
    VEHICLE_CLASSES = {2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}


class DetectionBoxesAdapter:
    """Lightweight adapter exposing xyxy, xywh, conf, and cls for BYTETracker."""
    def __init__(self, detections):
        if detections:
            xyxy_list = [[d.x1, d.y1, d.x2, d.y2] for d in detections]
            conf_list = [d.confidence for d in detections]
            cls_list = [float(d.class_id) for d in detections]

            self.xyxy = torch.as_tensor(xyxy_list, dtype=torch.float32)
            self.conf = torch.as_tensor(conf_list, dtype=torch.float32)
            self.cls = torch.as_tensor(cls_list, dtype=torch.float32)

            x1, y1, x2, y2 = self.xyxy[:, 0], self.xyxy[:, 1], self.xyxy[:, 2], self.xyxy[:, 3]
            w = x2 - x1
            h = y2 - y1
            cx = x1 + w / 2.0
            cy = y1 + h / 2.0
            self.xywh = torch.stack([cx, cy, w, h], dim=-1)
        else:
            self.xyxy = torch.empty((0, 4), dtype=torch.float32)
            self.conf = torch.empty((0,), dtype=torch.float32)
            self.cls = torch.empty((0,), dtype=torch.float32)
            self.xywh = torch.empty((0, 4), dtype=torch.float32)

    def __len__(self):
        return len(self.conf)

    def __getitem__(self, idx):
        sub = DetectionBoxesAdapter([])
        sub.xyxy = self.xyxy[idx]
        sub.conf = self.conf[idx]
        sub.cls = self.cls[idx]
        sub.xywh = self.xywh[idx]
        return sub


class CameraByteTracker:
    """Independent single-camera ByteTrack instance with PTS gap & epoch protection."""

    def __init__(
        self,
        camera_id: str,
        max_track_gap_ms: float = 1500.0,
        track_thresh: float = 0.25,
        match_thresh: float = 0.8,
        track_buffer: int = 30,
        sampling_interval_ms: float = 150.0,
        frame_rate: Optional[int] = None,
    ):
        self.camera_id = camera_id
        self.max_track_gap_ms = max_track_gap_ms
        self.sampling_interval_ms = sampling_interval_ms
        self.frame_rate = frame_rate or max(1, int(round(1000.0 / sampling_interval_ms)))

        self.args = SimpleNamespace(
            tracker_type='bytetrack',
            track_high_thresh=track_thresh,
            track_low_thresh=0.1,
            new_track_thresh=track_thresh,
            track_buffer=track_buffer,
            match_thresh=match_thresh,
            gmc_method='sparseOptFlow',
            proximity_thresh=0.5,
            appearance_thresh=0.25,
            with_reid=False,
            fuse_score=True,
        )

        self.tracker = BYTETracker(self.args, frame_rate=self.frame_rate)

        self.last_pts_ms: Optional[float] = None
        self.last_epoch: int = 0
        self.first_seen_pts: dict[int, float] = {}
        self.last_seen_pts: dict[int, float] = {}

    def reset(self):
        """Resets tracker state, clearing active tracklets and internal Kalman filters."""
        self.tracker.reset()
        self.last_pts_ms = None
        self.first_seen_pts.clear()
        self.last_seen_pts.clear()

    def update(self, packet, detections: list) -> list[VehicleTrack]:
        """
        Updates the camera's ByteTrack state with new vehicle detections.
        Applies epoch reset and abnormal PTS gap invalidation before matching.
        """
        # Protection 1: Stream epoch change -> Reset tracker
        if packet.stream_epoch != self.last_epoch:
            self.reset()
            self.last_epoch = packet.stream_epoch

        # Protection 2: Abnormal PTS gap (> 1500ms by default) -> Reset tracker
        if self.last_pts_ms is not None:
            gap = packet.pts_ms - self.last_pts_ms
            if gap > self.max_track_gap_ms or gap < 0:
                self.reset()

        self.last_pts_ms = packet.pts_ms

        if not detections:
            # Update tracker with empty boxes to allow tracklet aging
            empty_boxes = DetectionBoxesAdapter([])
            self.tracker.update(empty_boxes)
            return []

        boxes_adapter = DetectionBoxesAdapter(detections)
        tracked_np = self.tracker.update(boxes_adapter)

        tracks = []
        if tracked_np is None or len(tracked_np) == 0:
            return tracks

        # Periodic cleanup of inactive tracks (prune tracks not seen in the last 60 seconds)
        if len(self.last_seen_pts) > 1000:
            cutoff = packet.pts_ms - 60000.0
            inactive_ids = [tid for tid, last_pts in self.last_seen_pts.items() if last_pts < cutoff]
            for tid in inactive_ids:
                self.last_seen_pts.pop(tid, None)
                self.first_seen_pts.pop(tid, None)

        for row in tracked_np:
            # row: [x1, y1, x2, y2, track_id, conf, cls_id, det_idx]
            x1, y1, x2, y2, track_id, conf, cls_id = row[:7]
            track_id = int(track_id)
            cls_id = int(cls_id)
            conf = float(conf)

            if track_id not in self.first_seen_pts:
                self.first_seen_pts[track_id] = packet.pts_ms
            self.last_seen_pts[track_id] = packet.pts_ms

            class_name = VEHICLE_CLASSES.get(cls_id, f'vehicle_{cls_id}')

            vt = VehicleTrack(
                camera_id=packet.camera_id,
                track_id=track_id,
                stream_epoch=packet.stream_epoch,
                first_pts_ms=self.first_seen_pts[track_id],
                last_pts_ms=packet.pts_ms,
                class_id=cls_id,
                class_name=class_name,
                confidence=conf,
                x1=float(x1),
                y1=float(y1),
                x2=float(x2),
                y2=float(y2),
                age_frames=1,
            )
            tracks.append(vt)

        return tracks


class CameraTrackerRegistry:
    """Manages independent ByteTrack instances for each camera with cadence awareness."""

    def __init__(
        self,
        max_track_gap_ms: float = 1500.0,
        track_thresh: float = 0.25,
        sampling_interval_ms: float = 150.0,
    ):
        self.trackers: dict[str, CameraByteTracker] = {}
        self.max_track_gap_ms = max_track_gap_ms
        self.track_thresh = track_thresh
        self.sampling_interval_ms = sampling_interval_ms

    def get_tracker(self, camera_id: str) -> CameraByteTracker:
        if camera_id not in self.trackers:
            self.trackers[camera_id] = CameraByteTracker(
                camera_id=camera_id,
                max_track_gap_ms=self.max_track_gap_ms,
                track_thresh=self.track_thresh,
                sampling_interval_ms=self.sampling_interval_ms,
            )
        return self.trackers[camera_id]


    def update(self, packet, detections: list) -> list[VehicleTrack]:
        tracker = self.get_tracker(packet.camera_id)
        return tracker.update(packet, detections)

    def reset(self, camera_id: Optional[str] = None):
        if camera_id:
            if camera_id in self.trackers:
                self.trackers[camera_id].reset()
        else:
            for t in self.trackers.values():
                t.reset()
