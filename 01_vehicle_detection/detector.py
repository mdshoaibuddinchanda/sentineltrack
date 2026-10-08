import sys
from pathlib import Path
from typing import List, Optional, Union, Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from .models import VehicleDetection
except (ImportError, ValueError):
    from models import VehicleDetection

from ultralytics import YOLO

VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}
VEHICLE_CLASS_IDS = list(VEHICLE_CLASSES.keys())


class VehicleDetector:
    """
    Optimized YOLO11m vehicle detection subsystem.
    Supports FP16 precision, in-engine NMS class filtering, and dynamic batch inference.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence: float = 0.25,
        imgsz: int = 960,
        device: Optional[str] = None,
        half: bool = False
    ):
        resolved_model_path = model_path or str(ROOT_DIR / "models" / "vehicle" / "yolo11m.pt")
        self.model_path = resolved_model_path
        self.model = YOLO(resolved_model_path)
        self.confidence = confidence
        self.imgsz = imgsz
        self.device = device
        self.half = half

    def detect(self, packet) -> List[VehicleDetection]:
        """Detects vehicles in a single FramePacket."""
        batch_results = self.detect_batch([packet])
        return batch_results[0] if batch_results else []

    def detect_batch(self, packets: List[Any]) -> List[List[VehicleDetection]]:
        """
        Batch vehicle detection across multiple FramePackets.
        Preserves camera_id, stream_epoch, and PTS for every detected vehicle.
        """
        valid_indices = []
        valid_frames = []
        for idx, p in enumerate(packets):
            if p is not None and hasattr(p, 'frame') and p.frame is not None and p.frame.size > 0:
                valid_indices.append(idx)
                valid_frames.append(p.frame)

        all_detections: List[List[VehicleDetection]] = [[] for _ in range(len(packets))]
        if not valid_frames:
            return all_detections

        results = self.model.predict(
            source=valid_frames,
            conf=self.confidence,
            imgsz=self.imgsz,
            device=self.device,
            classes=VEHICLE_CLASS_IDS,
            half=self.half,
            verbose=False,
        )

        for orig_idx, result in zip(valid_indices, results):
            packet = packets[orig_idx]
            detections = []

            if result.boxes is not None:
                for box in result.boxes:
                    class_id = int(box.cls.item())
                    if class_id not in VEHICLE_CLASSES:
                        continue

                    confidence = float(box.conf.item())
                    x1, y1, x2, y2 = box.xyxy[0].cpu().tolist()

                    detections.append(
                        VehicleDetection(
                            camera_id=packet.camera_id,
                            pts_ms=packet.pts_ms,
                            stream_epoch=packet.stream_epoch,
                            class_id=class_id,
                            class_name=VEHICLE_CLASSES[class_id],
                            confidence=confidence,
                            x1=x1,
                            y1=y1,
                            x2=x2,
                            y2=y2,
                        )
                    )

            all_detections[orig_idx] = detections

        return all_detections

