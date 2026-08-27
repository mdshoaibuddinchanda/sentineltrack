import sys
from pathlib import Path

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


class VehicleDetector:

    def __init__(
        self,
        model_path: str = "yolo11m.pt",
        confidence: float = 0.25,
        imgsz: int = 960,
        device: str | None = None,
    ):
        self.model_path = model_path
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.imgsz = imgsz
        self.device = device

    def detect(self, packet) -> list[VehicleDetection]:
        results = self.model.predict(
            source=packet.frame,
            conf=self.confidence,
            imgsz=self.imgsz,
            device=self.device,
            verbose=False,
        )

        detections = []
        if not results:
            return detections

        result = results[0]
        if result.boxes is None:
            return detections

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

        return detections
