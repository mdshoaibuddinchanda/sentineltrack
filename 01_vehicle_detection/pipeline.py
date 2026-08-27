import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from .detector import VehicleDetector
    from .models import VehicleDetection
except (ImportError, ValueError):
    from detector import VehicleDetector
    from models import VehicleDetection


class VehicleDetectionPipeline:

    def __init__(self, detector: VehicleDetector):
        self.detector = detector

    def process(self, packet) -> list[VehicleDetection]:
        detections = self.detector.detect(packet)
        return detections
