import sys
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import importlib
try:
    models_mod = importlib.import_module("02_tracking.models")
    tracker_mod = importlib.import_module("02_tracking.tracker")
    manager_mod = importlib.import_module("02_tracking.track_manager")

    VehicleTrack = models_mod.VehicleTrack
    CameraTrackerRegistry = tracker_mod.CameraTrackerRegistry
    TrackManager = manager_mod.TrackManager
except Exception:
    from .models import VehicleTrack
    from .tracker import CameraTrackerRegistry
    from .track_manager import TrackManager



class VehicleTrackingPipeline:
    """
    End-to-end single-frame processing pipeline:
    FramePacket -> VehicleDetector -> VehicleDetection[] -> CameraTrackerRegistry (ByteTrack) -> TrackManager -> VehicleTrack[]
    """

    def __init__(
        self,
        detector,
        tracker_registry: Optional[CameraTrackerRegistry] = None,
        track_manager: Optional[TrackManager] = None,
    ):
        self.detector = detector
        self.tracker_registry = tracker_registry or CameraTrackerRegistry()
        self.track_manager = track_manager or TrackManager()

    def process(self, packet) -> list[VehicleTrack]:
        # 1. Detect vehicles
        detections = self.detector.detect(packet)

        # 2. Track per camera
        raw_tracks = self.tracker_registry.update(packet, detections)

        # 3. Update persistent track state & trails
        managed_tracks = [
            self.track_manager.update(t)
            for t in raw_tracks
        ]

        return managed_tracks

    def reset_camera(self, camera_id: str):
        self.tracker_registry.reset(camera_id)
        self.track_manager.reset_camera(camera_id)
